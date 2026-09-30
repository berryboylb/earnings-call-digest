"""Finding where the Q&A section starts."""

from __future__ import annotations

from .patterns import OPERATOR, QA_START_PHRASES
from .turns import Turn


def find_qa_start(turns: list[Turn]) -> int | None:
    """Index of the first Q&A turn, or None.

    Q&A starts at an explicit header, or at the first Operator turn that uses
    opening-Q&A wording, whichever comes first. The Operator turn only counts
    after someone else has spoken, because the Operator's welcome often says
    "there will be a question-and-answer session later".
    """
    header = next((i for i, t in enumerate(turns) if t.after_qa_header), None)
    handoff, someone_spoke = None, False
    for i, t in enumerate(turns):
        if t.speaker != OPERATOR:
            someone_spoke = True
        elif someone_spoke and QA_START_PHRASES.search(" ".join(t.lines)):
            handoff = i
            break
    found = [i for i in (header, handoff) if i is not None]
    return min(found) if found else None
