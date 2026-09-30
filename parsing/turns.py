"""Splitting the transcript body into speaker turns."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .names import contains, looks_like_name, looks_like_title, name_key, split_name_title
from .patterns import (
    INLINE_SPEAKER,
    MIN_LABEL_OCCURRENCES,
    OPERATOR,
    OPERATOR_LINE,
    QA_HEADER,
    UNIDENTIFIED,
)


@dataclass
class Turn:
    speaker: str
    after_qa_header: bool
    lines: list[str] = field(default_factory=list)


def _layout_a_names(line: str) -> list[str]:
    """Possible speaker names for a line that is only a name: "Name", "Name:" or "Name - Title"."""
    names = [line.removesuffix(":").strip()]
    split = split_name_title(line)
    if split and looks_like_title(split[1]):
        names.append(split[0])
    return names


def _count_labels(lines: list[str]) -> Counter:
    """Count how often each name-like label shows up as a possible speaker line."""
    counts: Counter = Counter()
    for raw in lines:
        line = raw.strip()
        names = _layout_a_names(line)
        if m := INLINE_SPEAKER.fullmatch(line):
            names.append(m["name"])
        for key in {name_key(n) for n in names if looks_like_name(n)}:
            counts[key] += 1
    return counts


def _accept_name(name: str, roster: dict, counts: Counter, current: Turn | None) -> str | None:
    """Return the speaker label if `name` is a speaker, else None.

    A name in the roster is always accepted. A name that isn't in the roster needs
    evidence that it really is a speaker: it appears as a label at least twice, or
    the turn in progress mentions it ("...comes from Alex Chen with Citi",
    "over to Marcus").
    """
    name = name.strip()
    key = name_key(name)
    if key in roster:
        return roster[key].name
    if UNIDENTIFIED.fullmatch(name):
        return name
    if not looks_like_name(name) or not key:
        return None
    if counts[key] >= MIN_LABEL_OCCURRENCES:
        return name
    if current is not None:
        said = name_key(" ".join(current.lines))
        if contains(said, key) or key[0] in said:
            return name
    return None


def _match_speaker(line: str, roster: dict, counts: Counter, current: Turn | None):
    """If `line` starts a new turn, return (speaker, inline text). Otherwise return None."""
    if m := OPERATOR_LINE.fullmatch(line):
        return OPERATOR, (m["text"] or "").strip()
    for name in _layout_a_names(line):
        if label := _accept_name(name, roster, counts, current):
            return label, ""
    if (m := INLINE_SPEAKER.fullmatch(line)) and (
        label := _accept_name(m["name"], roster, counts, current)
    ):
        return label, m["text"].strip()
    return None


def _looks_like_label(line: str) -> bool:
    """True if `line` has the shape of a speaker line, whether or not it was accepted."""
    names = _layout_a_names(line)
    if m := INLINE_SPEAKER.fullmatch(line):
        names.append(m["name"])
    return any(looks_like_name(n.strip()) for n in names)


def split_turns(lines: list[str], roster: dict, first_line_no: int) -> tuple[list[Turn], list[str]]:
    """Split body lines into turns. `first_line_no` is the file line number of lines[0], used in warnings."""
    counts = _count_labels(lines)
    canonical: dict[tuple[str, ...], str] = {}  # first spelling seen for each speaker
    turns: list[Turn] = []
    warnings: list[str] = []
    qa_header_seen = False
    for line_no, raw in enumerate(lines, start=first_line_no):
        line = raw.strip()
        if QA_HEADER.fullmatch(line):
            qa_header_seen = True
            continue
        current = turns[-1] if turns else None
        match = _match_speaker(line, roster, counts, current) if line else None
        if match:
            speaker, inline = match
            speaker = canonical.setdefault(name_key(speaker), speaker)
            turns.append(Turn(speaker, qa_header_seen, [inline] if inline else []))
        elif current is not None:
            if line and _looks_like_label(line):
                warnings.append(
                    f"Possible speaker line not recognised: '{line}' (line {line_no}), "
                    f"text attributed to {current.speaker}"
                )
            current.lines.append(line)
        # Text before the first speaker (title lines) is ignored.
    return turns, warnings
