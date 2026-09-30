"""Reading the participant list that gives each person's role."""

from __future__ import annotations

from .models import Participant, Role
from .names import looks_like_title, name_key, split_name_title
from .patterns import (
    ANALYST_HEADER,
    MANAGEMENT_HEADER,
    MIN_UNRECOGNISED_ROSTER_ENTRIES,
    OPERATOR_LINE,
)


def parse_roster(lines: list[str]) -> tuple[list[Participant], int]:
    """Read the participant list. Returns (participants, index of the first line after it).

    The block begins at a known header, and must come before the first Operator
    line. It ends at the first line that isn't a header, an entry or a blank line.
    It also ends at a repeated name, because that line is the first speaker line
    ("Jane Doe - CFO").
    """
    participants: list[Participant] = []
    seen: set[tuple[str, ...]] = set()
    role: Role | None = None
    last = -1
    for i, raw in enumerate(lines):
        line = raw.strip()
        header = line.removesuffix(":").strip()
        if MANAGEMENT_HEADER.fullmatch(header):
            role, last = "management", i
            continue
        if ANALYST_HEADER.fullmatch(header):
            role, last = "analyst", i
            continue
        if role is None:
            if OPERATOR_LINE.fullmatch(line):
                break  # the call has started and there was no participant list
            continue
        if not line:
            continue
        entry = split_name_title(line)
        if entry is None or name_key(entry[0]) in seen:
            break
        seen.add(name_key(entry[0]))
        participants.append(Participant(entry[0], entry[1], role))
        last = i
    return participants, last + 1


def find_unrecognised_roster(lines: list[str]) -> tuple[list[str], int]:
    """Look for what seems to be a participant list under a header we don't recognise.

    Before the first Operator line, a run of "Name - Title" lines (blank lines allowed)
    under some other header looks like a participant list. We don't know which role
    its header means, so no roles are taken from it; it only produces a warning.
    Turn detection still starts after it, so its lines don't become speaker turns.
    Returns (warnings, index of the first line after the last such block, or 0).
    """
    blocks: list[tuple[str, int, int]] = []  # (header, entry count, index after last entry)
    header, count, end = "", 0, 0
    for i, raw in enumerate(lines):
        line = raw.strip()
        if OPERATOR_LINE.fullmatch(line):
            break
        if not line:
            continue
        entry = split_name_title(line)
        if entry and looks_like_title(entry[1]):
            count, end = count + 1, i + 1
            continue
        if count:
            blocks.append((header, count, end))
        header, count = line, 0
    if count:
        blocks.append((header, count, end))

    lists = [(h, e) for h, n, e in blocks if n >= MIN_UNRECOGNISED_ROSTER_ENTRIES]
    warnings = [
        f"Possible participant list under unrecognised header '{h}'; roles not assigned from it"
        for h, _ in lists
    ]
    return warnings, max((e for _, e in lists), default=0)
