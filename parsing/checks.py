"""Final checks: fail loudly on untrustworthy results and warn about quality issues."""

from __future__ import annotations

from .models import ParseError, Segment
from .patterns import MIN_WORDS, SENTENCE_END


def validate(segments: list[Segment], speakers: list[str]) -> None:
    """Raise ParseError if the result is too thin to trust."""
    if len(speakers) < 2:
        raise ParseError(f"Only {len(speakers)} distinct speaker found; need at least 2.")
    if len(segments) < 3:
        raise ParseError(f"Only {len(segments)} segments found; need at least 3.")
    if not any(s.role == "management" for s in segments):
        raise ParseError("No management speaker identified.")


def quality_warnings(
    segments: list[Segment], unknown_speakers: list[str], has_participant_list: bool
) -> list[str]:
    """Warnings about a result that parsed but may be incomplete or uncertain."""
    warnings = []
    if unknown_speakers:
        warnings.append(f"Could not determine role for: {', '.join(unknown_speakers)}")
    if not has_participant_list:
        warnings.append("No participant list found; roles inferred heuristically.")
    words = sum(len(p.text.split()) for s in segments for p in s.paragraphs)
    if words < MIN_WORDS:
        warnings.append(f"Transcript is short ({words:,} words < {MIN_WORDS:,}); it may be incomplete.")
    last = segments[-1].paragraphs[-1].text
    if not SENTENCE_END.search(last):
        warnings.append(f"Last paragraph ends mid-sentence ('...{last[-40:]}'); transcript may be truncated.")
    if not any(s.role == "analyst" and s.section == "qa" for s in segments):
        warnings.append("No analyst turns found in Q&A.")
    return warnings
