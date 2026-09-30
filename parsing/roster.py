"""Reading the participant list that gives each person's role."""

from __future__ import annotations

from .models import Participant, Role
from .names import name_key, split_name_title
from .patterns import ANALYST_HEADER, MANAGEMENT_HEADER, OPERATOR_LINE


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

