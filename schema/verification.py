"""The shape of verification results: each extracted item, checked against the transcript."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

ItemKind = Literal["figure", "guidance", "risk", "qa"]


@dataclass
class Amount:
    """A number read from text, fully scaled: "$1.6 billion" has value 1_600_000_000."""

    raw: str  # the text it was read from, e.g. "$1.6 billion"
    value: float  # never negative; see direction
    unit: str  # "currency", "percent", "percentage_points", "bps" or "number"
    currency: str | None  # "USD", "EUR"... for currency amounts, if the text says
    direction: str | None  # "up" or "down" if the text says ("up 12%"), otherwise None
    start: int  # position of the amount in the text it was read from
    end: int
    scale: float = 1.0  # what the number was multiplied by: 1e9 for "billion"


class SourceMatch(BaseModel):
    """Where a quote was found in the transcript."""

    segment_id: str
    paragraph_index: int
    start: int  # character positions in the paragraph's text
    end: int
    text: str  # the transcript's own text at that position
    method: Literal["exact", "fuzzy"]
    score: float  # 1.0 for an exact match
    in_boilerplate: bool


class VerifiedItem(BaseModel):
    """One extracted item and the result of checking it."""

    id: str = ""
    kind: ItemKind
    status: Literal["verified", "unverified"] = "verified"
    reasons: list[str] = Field(default_factory=list)  # why it failed a check; any reason means unverified
    notes: list[str] = Field(default_factory=list)  # observations that don't block it
    fields: dict  # the item exactly as the model returned it
    speaker_claimed: str  # the speaker the model named
    speaker: str | None = None  # the speaker of the segment the quote was found in
    source: SourceMatch | None = None
    context: list[SourceMatch] = Field(default_factory=list)
    origin: Literal["prepared", "qa"]

    def update_status(self) -> None:
        self.status = "unverified" if self.reasons else "verified"


class MissedCandidate(BaseModel):
    """A number management said that no extracted item covers. For human review."""

    segment_id: str
    speaker: str
    raw: str
    context: str


class VerificationResult(BaseModel):
    items: list[VerifiedItem]
    possibly_missed: list[MissedCandidate]
    section_status: dict[str, str]  # copied from the extraction run: "ok", "partial", "failed" or "empty_input"
    failed_calls: dict[str, list[str]] = Field(default_factory=dict)  # section -> labels of calls that failed
