"""Stage 1: split a raw earnings call transcript into speaker segments.

No AI here. Later stages check every extracted quote against these segments, so the
parser has to be explicit about WHO said WHAT and in WHICH section. When it can't be
sure, it adds a warning or raises ParseError. It never guesses silently.
"""

from __future__ import annotations

from pathlib import Path

from .checks import quality_warnings, validate
from .models import Paragraph, ParsedTranscript, ParseError, Section, Segment
from .names import name_key
from .paragraphs import split_paragraphs
from .patterns import NBSP_CHARS
from .roles import assign_roles
from .roster import parse_roster
from .sections import find_qa_start
from .turns import Turn, split_turns


def _normalise(text: str) -> str:
    """Remove the BOM, unify line endings, and replace non-breaking spaces with spaces."""
    text = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    for nbsp in NBSP_CHARS:
        text = text.replace(nbsp, " ")
    return "\n".join(line.rstrip() for line in text.split("\n"))


def _drop_empty_turns(
    turns: list[Turn], warnings: list[str]
) -> tuple[list[Turn], list[list[Paragraph]]]:
    """Split each turn into paragraphs once, and drop turns that have none."""
    paragraphs = [split_paragraphs(t.lines) for t in turns]
    silent = [t.speaker for t, p in zip(turns, paragraphs) if not p]
    if silent:
        warnings.append(f"Dropped speaker lines with no text: {', '.join(silent)}")
    kept = [(t, p) for t, p in zip(turns, paragraphs) if p]
    if not kept:
        raise ParseError("No speaker turns found; is this an earnings call transcript?")
    return [t for t, _ in kept], [p for _, p in kept]


def _label_sections(turns: list[Turn], warnings: list[str]) -> list[Section]:
    qa_start = find_qa_start(turns)
    if qa_start is None:
        warnings.append("No Q&A section found; all segments marked 'prepared'.")
        qa_start = len(turns)
    return ["qa" if i >= qa_start else "prepared" for i in range(len(turns))]


def parse_transcript(text: str) -> ParsedTranscript:
    """Parse transcript text into speaker segments. Raises ParseError if the result can't be trusted."""
    lines = _normalise(text).split("\n")

    participants, body_start = parse_roster(lines)
    roster = {name_key(p.name): p for p in participants}

    turns, warnings = split_turns(lines[body_start:], roster, first_line_no=body_start + 1)
    turns, paragraphs = _drop_empty_turns(turns, warnings)

    sections = _label_sections(turns, warnings)
    roles = assign_roles(turns, sections, roster)

    segments = [
        Segment(f"S{i + 1}", t.speaker, roles[t.speaker], sections[i], paragraphs[i])
        for i, t in enumerate(turns)
    ]

    speakers = list(dict.fromkeys(s.speaker for s in segments))
    validate(segments, speakers)
    unknown = [s for s in speakers if roles[s] == "unknown"]
    warnings += quality_warnings(segments, unknown, has_participant_list=bool(participants))

    return ParsedTranscript(
        participants=participants,
        segments=segments,
        roster_source="participant_list" if participants else "heuristic",
        unknown_speakers=unknown,
        warnings=warnings,
    )


def parse_file(path: str | Path) -> ParsedTranscript:
    return parse_transcript(Path(path).read_text(encoding="utf-8-sig"))
