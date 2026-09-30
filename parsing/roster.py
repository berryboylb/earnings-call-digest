"""Reads the participant list, which says each person's role."""

from constants.parsing import (
    ANALYST_HEADER,
    MANAGEMENT_HEADER,
    MIN_UNRECOGNISED_ROSTER_ENTRIES,
    OPERATOR_LINE,
)
from schema.transcript import Participant
from utils.names import looks_like_title, name_key, split_name_title


def parse_roster(lines: list[str]) -> tuple[list[Participant], int]:
    """Read the participant list at the top of the transcript.

    Returns the participants and the index of the first line after the list.

    The list starts at a header such as "Company Participants", and must come before
    the call starts (the first "Operator" line). It ends at the first line that isn't
    a header, a "Name - Title" entry or blank. It also ends at a name that is already
    listed, because that line is the first speaker ("Jane Doe - CFO").
    """
    participants = []
    names_seen = set()
    current_role = None  # the role of the header we're under; None until we find one
    last_list_line = -1

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        header = line.removesuffix(":").strip()

        if MANAGEMENT_HEADER.fullmatch(header):
            current_role = "management"
            last_list_line = i
            continue
        if ANALYST_HEADER.fullmatch(header):
            current_role = "analyst"
            last_list_line = i
            continue

        if current_role is None:
            if OPERATOR_LINE.fullmatch(line):
                break  # the call has started and there was no participant list
            continue

        if not line:
            continue
        entry = split_name_title(line)
        if entry is None:
            break
        name, title = entry
        if name_key(name) in names_seen:
            break
        names_seen.add(name_key(name))
        participants.append(Participant(name, title, current_role))
        last_list_line = i

    return participants, last_list_line + 1


def find_unrecognised_roster(lines: list[str]) -> tuple[list[str], int]:
    """Find "Name - Title" lists under headers we don't recognise.

    Before the call starts, several "Name - Title" lines in a row look like a
    participant list. We don't know which role an unfamiliar header means, so no
    roles are taken from it; it only produces a warning. The parser still starts
    looking for speakers after it, so its lines don't become speaker turns.

    Returns (warnings, index of the first line after the last such list, or 0).
    """
    lists_found = []  # (header, index of the first line after the list)
    header = ""
    entries = 0
    end = 0

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if OPERATOR_LINE.fullmatch(line):
            break
        if not line:
            continue

        entry = split_name_title(line)
        if entry and looks_like_title(entry[1]):
            entries += 1
            end = i + 1
            continue

        # Any other line ends the current run of entries, and may be the next list's header.
        if entries >= MIN_UNRECOGNISED_ROSTER_ENTRIES:
            lists_found.append((header, end))
        header = line
        entries = 0

    if entries >= MIN_UNRECOGNISED_ROSTER_ENTRIES:
        lists_found.append((header, end))

    warnings = []
    for list_header, _ in lists_found:
        warnings.append(
            f"Possible participant list under unrecognised header '{list_header}'; roles not assigned from it"
        )
    last_list_end = max((list_end for _, list_end in lists_found), default=0)
    return warnings, last_list_end
