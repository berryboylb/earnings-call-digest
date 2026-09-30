"""Runs the LLM over the prepared remarks and the Q&A of a parsed transcript.

Prepared remarks: one call per speaker turn. A turn longer than MAX_WORDS_PER_CALL words
is split into parts at paragraph boundaries, and every part after the first also gets the
paragraphs just before it as read-only context. Q&A: one call for the whole section.
"""

import dataclasses
import json
from dataclasses import dataclass

from constants.extraction import CONTEXT_PARAGRAPHS, MAX_WORDS_PER_CALL
from constants.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from extraction.messages import build_user_message, render_segments
from parsing.paragraphs import segment_text
from providers.base import LlmError, Provider
from schema.extraction import (
    CallRecord,
    Extraction,
    ExtractionRun,
    SectionName,
    SectionResult,
)
from schema.transcript import Paragraph, ParsedTranscript, Segment


@dataclass
class Call:
    """One request to the LLM."""

    name: str  # shown in progress lines, e.g. "prepared S4 part 2 of 3, 2,410 words"
    label: str  # shown when it fails, e.g. "S4 part 2 of 3"; empty for a whole section
    segments: list[Segment]  # the text to extract from
    context: list[Segment]  # read-only text from just before it; may be empty


def run_extraction(parsed: ParsedTranscript, provider: Provider) -> ExtractionRun:
    """Extract figures, guidance, risks and Q&A topics from the prepared remarks and the Q&A."""
    inputs = section_inputs(parsed)
    sections = [
        _run_calls("prepared", _prepared_calls(inputs["prepared"]), provider),
        _run_calls("qa", _whole_section_calls("qa", inputs["qa"]), provider),
    ]

    modes_used = []
    for section in sections:
        if section.structured_output_mode and section.structured_output_mode not in modes_used:
            modes_used.append(section.structured_output_mode)

    return ExtractionRun(
        sections=sections,
        model=provider.model,
        fallback_models=provider.fallback_models,
        prompt_version=PROMPT_VERSION,
        structured_output_mode=", ".join(modes_used) or None,
        usage=provider.usage.model_copy(),
    )


def section_inputs(parsed: ParsedTranscript) -> dict[SectionName, list[Segment]]:
    """The segments sent for each section: the prepared remarks without the Operator,
    and all of Q&A (Operator and analysts included, so the model can see who asked)."""
    prepared = []
    qa = []
    for segment in parsed.segments:
        if segment.section == "prepared" and segment.role != "operator":
            prepared.append(segment)
        if segment.section == "qa":
            qa.append(segment)
    return {"prepared": prepared, "qa": qa}


# --- Planning the calls ---------------------------------------------------------------------

def _prepared_calls(segments: list[Segment]) -> list[Call]:
    """One call per speaker turn, or one per part of a long turn."""
    calls = []
    for segment in segments:
        parts = _split_into_parts(segment.paragraphs)
        for i, paragraphs in enumerate(parts):
            part = _with_paragraphs(segment, paragraphs)
            if not render_segments([part]):
                continue  # nothing left once boilerplate is removed
            label = segment.id if len(parts) == 1 else f"{segment.id} part {i + 1} of {len(parts)}"
            context = []
            if i > 0:
                context = [_with_paragraphs(segment, parts[i - 1][-CONTEXT_PARAGRAPHS:])]
            calls.append(Call(
                name=f"prepared {label}, {_word_count(paragraphs):,} words",
                label=label,
                segments=[part],
                context=context,
            ))
    return calls


def _whole_section_calls(name: SectionName, segments: list[Segment]) -> list[Call]:
    if not render_segments(segments):
        return []
    return [Call(name=name, label="", segments=segments, context=[])]


def _split_into_parts(paragraphs: list[Paragraph]) -> list[list[Paragraph]]:
    """Group paragraphs into parts of at most MAX_WORDS_PER_CALL words, never splitting a
    paragraph. A single paragraph longer than the limit is a part of its own."""
    parts = []
    current = []
    words_in_current = 0
    for paragraph in paragraphs:
        words = len(paragraph.text.split())
        if current and words_in_current + words > MAX_WORDS_PER_CALL:
            parts.append(current)
            current = []
            words_in_current = 0
        current.append(paragraph)
        words_in_current += words
    if current:
        parts.append(current)
    return parts


def _with_paragraphs(segment: Segment, paragraphs: list[Paragraph]) -> Segment:
    return dataclasses.replace(segment, paragraphs=list(paragraphs))


def _word_count(paragraphs: list[Paragraph]) -> int:
    return len(segment_text(Segment("", "", "unknown", "prepared", list(paragraphs))).split())


# --- Running the calls ---------------------------------------------------------------------

def _run_calls(section: SectionName, calls: list[Call], provider: Provider) -> SectionResult:
    """Run a section's calls in order and merge their answers.

    "ok" if every call worked, "partial" if some failed (the others' items are kept),
    "failed" if all failed. A failure is never replaced by an empty result.
    """
    if not calls:
        return SectionResult(name=section, status="empty_input", extraction=None, error=None, replayed=False)

    extractions = []
    failures = []  # "S4 part 2 of 3: timed out after 600s"
    failed_calls = []
    failed_segments = []
    all_replayed = True
    models = []
    modes = []
    records = []

    for call in calls:
        user_message = build_user_message(section, call.segments, call.context)
        try:
            extraction, replayed = provider.complete(call.name, SYSTEM_PROMPT, user_message, Extraction)
        except LlmError as error:
            records.append(CallRecord(name=call.name, status="failed", error=str(error)))
            failures.append(f"{call.label}: {error}" if call.label else str(error))
            failed_calls.append(call.label or section)
            for segment in call.segments:
                if segment.id not in failed_segments:
                    failed_segments.append(segment.id)
            continue
        records.append(CallRecord(name=call.name, status="ok", model=provider.last_model,
                                  earlier_failures=list(provider.last_failures)))
        extractions.append(extraction)
        all_replayed = all_replayed and replayed
        if provider.last_model not in models:
            models.append(provider.last_model)
        if provider.last_mode not in modes:
            modes.append(provider.last_mode)

    error = "; ".join(failures) or None
    if not extractions:
        # Never return an empty Extraction here: a failure must look like a failure.
        return SectionResult(name=section, status="failed", extraction=None, error=error, replayed=False,
                             failed_calls=failed_calls, failed_segments=failed_segments, calls=records)

    return SectionResult(
        name=section,
        status="partial" if failures else "ok",
        extraction=_merge(extractions),
        error=error,
        replayed=all_replayed,
        model=", ".join(model for model in models if model) or None,
        structured_output_mode=", ".join(mode for mode in modes if mode) or None,
        failed_calls=failed_calls,
        failed_segments=failed_segments,
        calls=records,
    )


def _merge(extractions: list[Extraction]) -> Extraction:
    """All the calls' items, in the order the calls ran. An item that two calls returned
    identically (e.g. from overlapping context) is kept once."""
    merged = {"figures": [], "guidance": [], "risks": [], "qa_topics": []}
    seen = set()
    for extraction in extractions:
        for kind, items in merged.items():
            for item in getattr(extraction, kind):
                key = json.dumps([kind, item.model_dump()], sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    items.append(item)
    return Extraction(**merged)
