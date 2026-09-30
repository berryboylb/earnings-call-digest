"""Final checks on a parsed transcript: errors for results we can't trust, warnings for doubts."""

from constants.parsing import (
    MIN_SEGMENTS,
    MIN_SPEAKERS,
    MIN_WORDS,
    SENTENCE_END,
    TRUNCATION_PREVIEW_LENGTH,
)
from schema.transcript import ParseError, Segment


def validate(segments: list[Segment], speakers: list[str]) -> None:
    """Raise ParseError if the result is too thin to trust."""
    if len(speakers) < MIN_SPEAKERS:
        raise ParseError(f"Only {len(speakers)} distinct speaker found; need at least {MIN_SPEAKERS}.")
    if len(segments) < MIN_SEGMENTS:
        raise ParseError(f"Only {len(segments)} segments found; need at least {MIN_SEGMENTS}.")
    has_management = any(segment.role == "management" for segment in segments)
    if not has_management:
        raise ParseError("No management speaker identified.")


def quality_warnings(
    segments: list[Segment], unknown_speakers: list[str], has_participant_list: bool
) -> list[str]:
    """Warnings about a result that parsed, but may be incomplete or uncertain."""
    warnings = []

    if unknown_speakers:
        warnings.append(f"Could not determine role for: {', '.join(unknown_speakers)}")

    if not has_participant_list:
        warnings.append("No participant list found; roles inferred heuristically.")

    word_count = _count_words(segments)
    if word_count < MIN_WORDS:
        warnings.append(f"Transcript is short ({word_count:,} words < {MIN_WORDS:,}); it may be incomplete.")

    last_paragraph = segments[-1].paragraphs[-1].text
    if not SENTENCE_END.search(last_paragraph):
        ending = last_paragraph[-TRUNCATION_PREVIEW_LENGTH:]
        warnings.append(f"Last paragraph ends mid-sentence ('...{ending}'); transcript may be truncated.")

    has_analyst_in_qa = any(segment.role == "analyst" and segment.section == "qa" for segment in segments)
    if not has_analyst_in_qa:
        warnings.append("No analyst turns found in Q&A.")

    return warnings


def _count_words(segments: list[Segment]) -> int:
    total = 0
    for segment in segments:
        for paragraph in segment.paragraphs:
            total += len(paragraph.text.split())
    return total
