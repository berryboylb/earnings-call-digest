from pathlib import Path

from extraction.extractor import run_extraction
from parsing.parser import parse_file
from providers.base import LlmError
from schema.extraction import Extraction, Usage
from schema.transcript import Paragraph, ParsedTranscript, Segment

DATA = Path(__file__).parents[2] / "tests" / "fixtures"


class FakeProvider:
    """Records calls; raises LlmError for the section names in `fail`."""

    def __init__(self, fail=()):
        self.model, self.fallback_models, self.usage = "fake/model", [], Usage()
        self.last_model = self.last_mode = None
        self.last_failures = []
        self.fail, self.calls = set(fail), []

    def complete(self, name, system, user, schema):
        self.calls.append(name)
        if name in self.fail:
            raise LlmError("upstream timed out")
        self.last_model, self.last_mode = self.model, "json_schema"
        return Extraction(figures=[], guidance=[], risks=[], qa_topics=[]), False


def test_failure_in_qa_marks_only_qa_failed():
    provider = FakeProvider(fail={"qa"})
    run = run_extraction(parse_file(DATA / "meridian.txt"), provider)
    prepared, qa = run.sections
    assert (prepared.name, prepared.status, prepared.error) == ("prepared", "ok", None)
    assert prepared.extraction is not None
    assert (qa.name, qa.status, qa.error) == ("qa", "failed", "upstream timed out")
    assert qa.extraction is None  # never an empty Extraction standing in for a failure
    # one call per prepared-remarks speaker turn (the Operator's welcome is left out), then Q&A
    assert [name.split(",")[0] for name in provider.calls] == [
        "prepared S2", "prepared S3", "prepared S4", "prepared S5", "qa"]


def test_empty_qa_input_is_not_sent():
    segs = [Segment(f"S{i}", name, "management", "prepared", [Paragraph("Revenue was $5 million.")])
            for i, name in enumerate(["Jane Doe", "John Roe", "Jane Doe"], start=1)]
    parsed = ParsedTranscript(participants=[], segments=segs, roster_source="heuristic")
    provider = FakeProvider()
    run = run_extraction(parsed, provider)
    assert [(section.name, section.status) for section in run.sections] == [("prepared", "ok"), ("qa", "empty_input")]
    assert run.sections[1].extraction is None and run.sections[1].error is None
    assert [name.split(",")[0] for name in provider.calls] == ["prepared S1", "prepared S2", "prepared S3"]
