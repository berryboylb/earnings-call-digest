"""Finds where the Q&A part of the call starts."""

from constants.parsing import OPERATOR, QA_START_PHRASES
from parsing.speakers import Turn


def find_qa_start(turns: list[Turn]) -> int | None:
    """Return the index of the first Q&A turn, or None if the call has no Q&A.

    Q&A starts at whichever comes first:
    - the first turn after an explicit "Question-and-Answer Session" header, or
    - the first Operator turn that opens Q&A ("Our first question comes from...").
    """
    header_start = _first_turn_after_qa_header(turns)
    operator_start = _first_operator_qa_handoff(turns)
    if header_start is None:
        return operator_start
    if operator_start is None:
        return header_start
    return min(header_start, operator_start)


def _first_turn_after_qa_header(turns: list[Turn]) -> int | None:
    for i, turn in enumerate(turns):
        if turn.after_qa_header:
            return i
    return None


def _first_operator_qa_handoff(turns: list[Turn]) -> int | None:
    """The first Operator turn that opens Q&A. It only counts once someone else has
    spoken, because the Operator's welcome often says "there will be a Q&A later"."""
    someone_else_has_spoken = False
    for i, turn in enumerate(turns):
        if turn.speaker != OPERATOR:
            someone_else_has_spoken = True
        elif someone_else_has_spoken and QA_START_PHRASES.search(" ".join(turn.lines)):
            return i
    return None
