"""Splits the transcript into speaker turns, and decides each speaker's role."""

from collections import Counter
from dataclasses import dataclass, field

from constants.parsing import (
    END_MARKER,
    INLINE_SPEAKER,
    MIN_LABEL_OCCURRENCES,
    OPERATOR,
    OPERATOR_LINE,
    QA_HANDOFF_WORD,
    QA_HEADER,
    UNIDENTIFIED,
)
from schema.transcript import Participant, Role, Section
from utils.names import (
    contains_words,
    looks_like_name,
    looks_like_title,
    name_key,
    split_name_title,
)


@dataclass
class Turn:
    """One speaker's turn: who spoke, and the lines they said."""

    speaker: str
    after_qa_header: bool  # True if an explicit "Q&A" header came before this turn
    lines: list[str] = field(default_factory=list)


# --- Splitting into turns ---------------------------------------------------------

def split_turns(
    lines: list[str], roster: dict[tuple[str, ...], Participant], first_line_no: int
) -> tuple[list[Turn], list[str]]:
    """Split the transcript body into speaker turns.

    `first_line_no` is the line number of lines[0] in the file, used in warnings.
    Text before the first speaker (title lines) is ignored, and so is everything
    from an end marker such as "END OF TRANSCRIPT" on.
    """
    lines = _lines_before_end_marker(lines)
    label_counts = _count_speaker_labels(lines)
    # The first spelling seen for each person, so "Helen Ortiz" and "Helen M. Ortiz" are one speaker.
    first_spelling = {}
    turns = []
    warnings = []
    qa_header_seen = False

    for line_no, raw_line in enumerate(lines, start=first_line_no):
        line = raw_line.strip()
        if QA_HEADER.fullmatch(line):
            qa_header_seen = True
            continue

        current_turn = turns[-1] if turns else None
        speaker_line = _read_speaker_line(line, roster, label_counts, current_turn) if line else None

        if speaker_line:
            speaker, text_on_same_line = speaker_line
            speaker = first_spelling.setdefault(name_key(speaker), speaker)
            first_lines = [text_on_same_line] if text_on_same_line else []
            turns.append(Turn(speaker, qa_header_seen, first_lines))
        elif current_turn is not None:
            if line and _looks_like_speaker_line(line):
                warnings.append(
                    f"Possible speaker line not recognised: '{line}' (line {line_no}), "
                    f"text attributed to {current_turn.speaker}"
                )
            current_turn.lines.append(line)

    return turns, warnings


def _lines_before_end_marker(lines: list[str]) -> list[str]:
    for i, line in enumerate(lines):
        if END_MARKER.fullmatch(line.strip()):
            return lines[:i]
    return lines


def _read_speaker_line(
    line: str, roster: dict, label_counts: Counter, current_turn: Turn | None
) -> tuple[str, str] | None:
    """If the line starts a new turn, return (speaker, any text on the same line). Otherwise None."""
    operator = OPERATOR_LINE.fullmatch(line)
    if operator:
        return OPERATOR, (operator["text"] or "").strip()

    # The name on a line of its own: "Jane Doe", "Jane Doe:" or "Jane Doe - CFO".
    for name in _names_on_speaker_line(line):
        speaker = _confirmed_speaker(name, roster, label_counts, current_turn)
        if speaker:
            return speaker, ""

    # The name and text on one line: "Jane Doe: Revenue was..."
    inline = INLINE_SPEAKER.fullmatch(line)
    if inline:
        speaker = _confirmed_speaker(inline["name"], roster, label_counts, current_turn)
        if speaker:
            return speaker, inline["text"].strip()

    return None


def _confirmed_speaker(
    name: str, roster: dict, label_counts: Counter, current_turn: Turn | None
) -> str | None:
    """Return the speaker's name if `name` really is a speaker, otherwise None.

    Someone on the participant list is always a speaker. Anyone else needs evidence:
    their name appears as a speaker label at least MIN_LABEL_OCCURRENCES times, or the
    turn before mentions them ("...comes from Alex Chen with Citi", "over to Marcus").
    """
    name = name.strip()
    key = name_key(name)
    if key in roster:
        return roster[key].name
    if UNIDENTIFIED.fullmatch(name):
        return name
    if not key or not looks_like_name(name):
        return None
    if label_counts[key] >= MIN_LABEL_OCCURRENCES:
        return name

    if current_turn is not None:
        words_said = name_key(" ".join(current_turn.lines))
        full_name_mentioned = contains_words(words_said, key)
        first_name_mentioned = key[0] in words_said
        if full_name_mentioned or first_name_mentioned:
            return name
    return None


def _names_on_speaker_line(line: str) -> list[str]:
    """Possible names on a line that is only a speaker label: the whole line
    ("Jane Doe", "Jane Doe:"), plus the name in "Jane Doe - Chief Financial Officer"."""
    names = [line.removesuffix(":").strip()]
    name_and_title = split_name_title(line)
    if name_and_title and looks_like_title(name_and_title[1]):
        names.append(name_and_title[0])
    return names


def _all_possible_names(line: str) -> list[str]:
    """Every possible speaker name on a line, including "Jane Doe" in "Jane Doe: text"."""
    names = _names_on_speaker_line(line)
    inline = INLINE_SPEAKER.fullmatch(line)
    if inline:
        names.append(inline["name"])
    return names


def _count_speaker_labels(lines: list[str]) -> Counter:
    """Count how many lines each name appears on as a possible speaker label."""
    label_counts = Counter()
    for raw_line in lines:
        names = _all_possible_names(raw_line.strip())
        keys_on_this_line = {name_key(name) for name in names if looks_like_name(name)}
        for key in keys_on_this_line:
            label_counts[key] += 1
    return label_counts


def _looks_like_speaker_line(line: str) -> bool:
    """True if the line is shaped like a speaker label, even if it wasn't accepted as one."""
    for name in _all_possible_names(line):
        if looks_like_name(name):
            return True
    return False


# --- Roles ----------------------------------------------------------------------

def assign_roles(turns: list[Turn], sections: list[Section], roster: dict) -> dict[str, Role]:
    """Decide the role of every speaker."""
    roles = {}
    for turn in turns:
        if turn.speaker not in roles:
            roles[turn.speaker] = _role_of(turn.speaker, turns, sections, roster)
    return roles


def _role_of(speaker: str, turns: list[Turn], sections: list[Section], roster: dict) -> Role:
    if speaker == OPERATOR:
        return "operator"

    key = name_key(speaker)
    if key in roster:
        return roster[key].role
    if UNIDENTIFIED.fullmatch(speaker):
        return "unknown"
    if roster:
        return "unknown"  # there is a participant list, and this speaker isn't on it

    # No participant list, so work it out from how the call runs.
    if _introduced_as_questioner(speaker, turns, sections):
        return "analyst"
    if _speaks_before_qa(speaker, turns, sections):
        return "management"
    return "unknown"


def _introduced_as_questioner(speaker: str, turns: list[Turn], sections: list[Section]) -> bool:
    """True if the Operator names this speaker in a Q&A hand-off right before they speak."""
    speaker_key = name_key(speaker)
    for i in range(1, len(turns)):
        previous_turn, turn = turns[i - 1], turns[i]
        if turn.speaker != speaker or sections[i] != "qa" or previous_turn.speaker != OPERATOR:
            continue
        operator_text = " ".join(previous_turn.lines)
        if QA_HANDOFF_WORD in operator_text.lower() and contains_words(name_key(operator_text), speaker_key):
            return True
    return False


def _speaks_before_qa(speaker: str, turns: list[Turn], sections: list[Section]) -> bool:
    for turn, section in zip(turns, sections):
        if turn.speaker == speaker and section == "prepared":
            return True
    return False
