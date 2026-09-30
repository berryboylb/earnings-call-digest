"""Deciding each speaker's role."""

from __future__ import annotations

from .models import Role, Section
from .names import contains, name_key
from .patterns import OPERATOR, QA_HANDOFF_WORD, UNIDENTIFIED
from .turns import Turn


def _introduced_as_questioner(speaker: str, turns: list[Turn], sections: list[Section]) -> bool:
    """True if an Operator Q&A hand-off names `speaker` and they speak next."""
    key = name_key(speaker)
    for prev, turn, section in zip(turns, turns[1:], sections[1:]):
        if turn.speaker == speaker and section == "qa" and prev.speaker == OPERATOR:
            text = " ".join(prev.lines)
            if QA_HANDOFF_WORD in text.lower() and contains(name_key(text), key):
                return True
    return False


def assign_roles(turns: list[Turn], sections: list[Section], roster: dict) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for turn in turns:
        s = turn.speaker
        if s in roles:
            continue
        if s == OPERATOR:
            roles[s] = "operator"
        elif name_key(s) in roster:
            roles[s] = roster[name_key(s)].role
        elif UNIDENTIFIED.fullmatch(s):
            roles[s] = "analyst" if "analyst" in s.lower() else "unknown"
        elif roster:
            roles[s] = "unknown"  # a participant list exists, so roles come only from it
        elif _introduced_as_questioner(s, turns, sections):
            roles[s] = "analyst"
        elif any(t.speaker == s and sec == "prepared" for t, sec in zip(turns, sections)):
            roles[s] = "management"
        else:
            roles[s] = "unknown"
    return roles
