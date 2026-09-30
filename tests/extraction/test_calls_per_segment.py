"""The prepared remarks are extracted with one call per speaker turn, and a long turn is split
into parts. These tests use a fake provider, so nothing calls a real model."""

from datetime import datetime, timezone
from pathlib import Path

from constants.extraction import MAX_WORDS_PER_CALL
from extraction.extractor import run_extraction
from parsing.parser import parse_file
from providers.base import LlmError
from rendering.meta import answered_by
from rendering.view import build_view
from schema.digest import DigestMeta
from schema.extraction import Extraction, Usage
from schema.transcript import Paragraph, ParsedTranscript, Segment
from verification.verifier import verify_run

MERIDIAN = Path(__file__).parents[1] / "fixtures" / "meridian.txt"


class FakeProvider:
    """Answers each call with what `answers` returns for it; raises LlmError for calls in `fail`."""

    def __init__(self, answers=None, fail=()):
        self.model, self.fallback_models, self.usage = "fake/model", [], Usage()
        self.last_model = self.last_mode = None
        self.last_failures = []
        self.answers = answers or (lambda name, user: {})
        self.fail = fail
        self.calls = []  # (name, user message)

    def complete(self, name, system, user, schema):
        self.calls.append((name, user))
        if any(name.startswith(prefix) for prefix in self.fail):
            raise LlmError("timed out after 600s")
        self.last_model, self.last_mode = self.model, "json_schema"
        return Extraction(**{"figures": [], "guidance": [], "risks": [], "qa_topics": [], **self.answers(name, user)}), False


def figure(metric, quote, value="$1 million", speaker="Priya Shah"):
    return {"metric": metric, "value": value, "period": "Q2 2026", "is_comparison": False, "basis": "not stated",
            "speaker": speaker, "quote": quote, "context_quotes": []}


def transcript(*segments):
    return ParsedTranscript(participants=[], segments=list(segments), roster_source="heuristic")


def test_each_prepared_speaker_turn_is_its_own_call_merged_in_order():
    parsed = transcript(
        Segment("S1", "Jane Doe", "management", "prepared", [Paragraph("Revenue was $5 million.")]),
        Segment("S2", "John Roe", "management", "prepared", [Paragraph("Margin was 30%.")]),
    )
    provider = FakeProvider(answers=lambda name, user: {"figures": [figure(name.split(",")[0], "q")]})
    run = run_extraction(parsed, provider)

    assert [name for name, _ in provider.calls] == ["prepared S1, 4 words", "prepared S2, 3 words"]
    [prepared, qa] = run.sections
    assert [item.metric for item in prepared.extraction.figures] == ["prepared S1", "prepared S2"]
    assert (prepared.status, qa.status) == ("ok", "empty_input")


def test_a_long_turn_is_split_into_parts_with_preceding_context_and_duplicates_removed():
    paragraphs = [Paragraph(f"Paragraph {n} " + "word " * 297 + "end.") for n in range(1, 11)]  # 10 x 300 words
    parsed = transcript(Segment("S3", "Amy Hood", "management", "prepared", paragraphs))
    assert sum(len(p.text.split()) for p in paragraphs) > MAX_WORDS_PER_CALL

    same_item = figure("Revenue", "Paragraph 1 word word", speaker="Amy Hood")
    provider = FakeProvider(answers=lambda name, user: {"figures": [same_item]})
    run = run_extraction(parsed, provider)

    names = [name for name, _ in provider.calls]
    assert names == ["prepared S3 part 1 of 2, 2,400 words", "prepared S3 part 2 of 2, 600 words"]
    first_message, second_message = provider.calls[0][1], provider.calls[1][1]
    assert "<preceding_context>" not in first_message
    context = second_message.split("<preceding_context>")[1].split("</preceding_context>")[0]
    assert "Paragraph 7 " in context and "Paragraph 8 " in context  # the last 2 paragraphs of part 1
    assert "Paragraph 6 " not in context
    assert "Do not extract items from it." in second_message
    assert len(run.sections[0].extraction.figures) == 1  # returned by both parts, kept once


def test_one_failed_call_makes_the_section_partial_and_the_rest_is_still_shown():
    parsed = parse_file(MERIDIAN)  # prepared calls: S2 Emma, S3 Daniel, S4 Priya, S5 Daniel

    def answers(name, user):
        if name.startswith("prepared S4"):
            return {"figures": [figure("Operating cash flow", "Operating cash flow was $180 million.", "$180 million")]}
        return {}

    run = run_extraction(parsed, FakeProvider(answers=answers, fail=("prepared S3",)))
    prepared = run.sections[0]
    assert prepared.status == "partial"
    assert prepared.failed_calls == ["S3"] and prepared.failed_segments == ["S3"]
    assert prepared.error == "S3: timed out after 600s"

    result = verify_run(parsed, run)
    [item] = [item for item in result.items if item.kind == "figure"]
    assert item.status == "verified" and item.fields["metric"] == "Operating cash flow"
    assert all(missed.segment_id != "S3" for missed in result.possibly_missed)  # not "missed": never extracted

    meta = DigestMeta(call_title="Meridian", call_date="August 6, 2026", source="meridian.txt",
                      answered_by=answered_by(run), prompt_version="v3", structured_output_mode="json_schema",
                      replayed=False, transcript_sha256="abc")
    view = build_view(result, meta, datetime(2026, 9, 30, tzinfo=timezone.utc))
    assert view.banner == ("INCOMPLETE: extraction failed for part of the prepared remarks (S3). "
                           "Items from the other parts are shown; missing items may exist.")
    assert [row[0] for row in view.tables[0].rows] == ["Operating cash flow"]
    assert "prepared: fake/model (3 calls), 1 call failed" in view.footer
