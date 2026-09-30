"""Runs the LLM over the prepared remarks and the Q&A of a parsed transcript."""

from constants.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from extraction.messages import build_user_message, render_segments
from providers.base import LlmError, Provider
from schema.extraction import Extraction, ExtractionRun, SectionName, SectionResult
from schema.transcript import ParsedTranscript, Segment


def run_extraction(parsed: ParsedTranscript, provider: Provider) -> ExtractionRun:
    """Extract figures, guidance, risks and Q&A topics: one LLM call per section of the call."""
    sections = []
    for name, segments in section_inputs(parsed).items():
        sections.append(_run_section(name, segments, provider))

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


def _run_section(name: SectionName, segments: list[Segment], provider: Provider) -> SectionResult:
    if not render_segments(segments):
        return SectionResult(name=name, status="empty_input", extraction=None, error=None, replayed=False)

    user_message = build_user_message(name, segments)
    try:
        extraction, replayed = provider.complete(name, SYSTEM_PROMPT, user_message, Extraction)
    except LlmError as error:
        # Never return an empty Extraction here: a failure must look like a failure.
        return SectionResult(name=name, status="failed", extraction=None, error=str(error), replayed=False)

    return SectionResult(
        name=name,
        status="ok",
        extraction=extraction,
        error=None,
        replayed=replayed,
        model=provider.last_model,
        structured_output_mode=provider.last_mode,
    )
