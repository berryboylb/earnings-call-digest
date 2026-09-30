"""Data model for a parsed transcript. No logic here."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Role = Literal["management", "analyst", "operator", "unknown"]
Section = Literal["prepared", "qa"]


class ParseError(Exception):
    """Raised when a transcript can't be turned into a trustworthy result."""


@dataclass
class Participant:
    name: str
    title: str
    role: Role


@dataclass
class Paragraph:
    text: str
    # (start, end) character offsets into `text` of safe-harbor boilerplate.
    boilerplate_spans: list[tuple[int, int]] = field(default_factory=list)

    @property
    def boilerplate(self) -> bool:
        """True only if boilerplate covers the whole paragraph."""
        return any(s == 0 and e == len(self.text) for s, e in self.boilerplate_spans)


@dataclass
class Segment:
    id: str
    speaker: str
    role: Role
    section: Section
    paragraphs: list[Paragraph] = field(default_factory=list)


@dataclass
class ParsedTranscript:
    participants: list[Participant]
    segments: list[Segment]
    roster_source: Literal["participant_list", "heuristic"]
    unknown_speakers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
