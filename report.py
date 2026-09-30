"""Prints the results of each pipeline stage to the console."""

from constants.report import QUOTE_PREVIEW_LENGTH
from schema.extraction import Extraction, ExtractionRun
from schema.transcript import ParsedTranscript


def print_parse(parsed: ParsedTranscript) -> None:
    """One line per segment: id, speaker, role, section, and a mark per paragraph
    ("." normal, "B" all boilerplate, "b" partly boilerplate). Then the warnings."""
    segments = parsed.segments
    qa_count = sum(1 for segment in segments if segment.section == "qa")
    speaker_count = len({segment.speaker for segment in segments})
    print(f"{len(segments)} segments ({qa_count} in Q&A), {speaker_count} speakers, "
          f"roles from: {parsed.roster_source}")

    name_width = max(len(segment.speaker) for segment in segments)
    for segment in segments:
        marks = "".join(_paragraph_mark(paragraph) for paragraph in segment.paragraphs)
        print(f"  {segment.id:<4} {segment.speaker:<{name_width}}  {segment.role:<10}  "
              f"{segment.section:<8}  {marks}")

    for warning in parsed.warnings:
        print(f"  warning: {warning}")


def print_extraction(run: ExtractionRun) -> None:
    """The model and usage, then each section's status and the items it found."""
    fallbacks = ", ".join(run.fallback_models) or "none"
    print(f"model: {run.model} | fallback: {fallbacks} | prompt {run.prompt_version} | "
          f"structured output: {run.structured_output_mode}")
    usage = run.usage
    print(f"usage: {usage.calls} calls, {usage.replayed_calls} replayed, "
          f"{usage.prompt_tokens} prompt + {usage.completion_tokens} completion tokens")

    for section in run.sections:
        if section.extraction is None:
            detail = f"error: {section.error}" if section.error else "no input"
            print(f"\n[{section.name}] {section.status} | {detail}")
            continue

        source = "replayed" if section.replayed else "live"
        if section.model and section.model != run.model:
            source += f" | fallback model {section.model}"
        items = section.extraction
        print(f"\n[{section.name}] {section.status} | {source} | figures {len(items.figures)}, "
              f"guidance {len(items.guidance)}, risks {len(items.risks)}, qa_topics {len(items.qa_topics)}")
        for line in item_lines(items):
            print(f"  {line}")


def item_lines(extraction: Extraction) -> list[str]:
    """One line per item: kind | metric, theme or topic | value | period | speaker | start of quote."""
    rows = []
    for figure in extraction.figures:
        rows.append(["figure", figure.metric, figure.value, figure.period, figure.speaker, figure.quote])
    for guidance in extraction.guidance:
        rows.append(["guidance", guidance.metric, guidance.range, guidance.period, guidance.speaker, guidance.quote])
    for risk in extraction.risks:
        rows.append(["risk", risk.theme, risk.hedging_phrase, "-", risk.speaker, risk.quote])
    for topic in extraction.qa_topics:
        asked = f"asked by {topic.asked_by}, {topic.answer_quality}"
        rows.append(["qa_topic", topic.topic, asked, "-", topic.speaker, topic.quote])

    lines = []
    for row in rows:
        row[-1] = row[-1][:QUOTE_PREVIEW_LENGTH]
        lines.append(" | ".join(row))
    return lines


def _paragraph_mark(paragraph) -> str:
    if paragraph.boilerplate:
        return "B"
    if paragraph.boilerplate_spans:
        return "b"
    return "."
