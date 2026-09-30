"""Run extraction over the prepared-remarks and Q&A sections of a parsed transcript."""

from __future__ import annotations

from parsing import ParsedTranscript, Segment

from .client import LlmError, Provider
from .config import PROMPT_VERSION
from .models import Extraction, ExtractionRun, SectionName, SectionResult
from .prompts import SYSTEM_PROMPT, build_user_message, render_segments


def section_inputs(parsed: ParsedTranscript) -> dict[SectionName, list[Segment]]:
    """Prepared remarks without the operator; all of Q&A, so the model sees who asked."""
    return {
        "prepared": [s for s in parsed.segments if s.section == "prepared" and s.role != "operator"],
        "qa": [s for s in parsed.segments if s.section == "qa"],
    }


def _run_section(name: SectionName, segments: list[Segment], provider: Provider) -> SectionResult:
    if not render_segments(segments):
        return SectionResult(name=name, status="empty_input", extraction=None, error=None, replayed=False)
    try:
        extraction, replayed = provider.complete(
            name, SYSTEM_PROMPT, build_user_message(name, segments), Extraction
        )
    except LlmError as e:
        # Never substitute an empty Extraction: a failure must look like a failure.
        return SectionResult(name=name, status="failed", extraction=None, error=str(e), replayed=False)
    return SectionResult(name=name, status="ok", extraction=extraction, error=None, replayed=replayed)


def run_extraction(parsed: ParsedTranscript, provider: Provider) -> ExtractionRun:
    sections = [_run_section(name, segs, provider) for name, segs in section_inputs(parsed).items()]
    return ExtractionRun(
        sections=sections,
        model=provider.model,
        prompt_version=PROMPT_VERSION,
        structured_output_mode=provider.structured_output_mode,
        usage=provider.usage.model_copy(),
    )
