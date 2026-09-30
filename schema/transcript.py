"""The shape of a parsed transcript: participants, segments and paragraphs."""

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
    # Where the safe-harbor boilerplate is in `text`, as (start, end) character positions.
    boilerplate_spans: list[tuple[int, int]] = field(default_factory=list)

    @property
    def boilerplate(self) -> bool:
        """True only if the whole paragraph is boilerplate."""
        return (0, len(self.text)) in self.boilerplate_spans


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
