"""The shape of an answer key (data/<name>.gold.json) and of an evaluation against it."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- The answer key, written by hand ---------------------------------------------------
# anchor: a short verbatim snippet of the transcript that identifies the fact.
# period: one accepted wording, or a list of accepted wordings.

class GoldFigure(_Strict):
    anchor: str
    value: str
    period: str | list[str]
    basis: str


class GoldGuidance(_Strict):
    anchor: str
    range: str
    period: str | list[str]
    direction: str
    qualifier_anchor: str | None


class GoldRisk(_Strict):
    anchor: str
    theme: str  # a label for the report; not scored


class MustNot(_Strict):
    """A value that must never appear as a verified item of this kind."""

    kind: Literal["figure", "guidance"]
    value: str
    reason: str


class AnswerKey(_Strict):
    figures: list[GoldFigure] = Field(default_factory=list)
    guidance: list[GoldGuidance] = Field(default_factory=list)
    risks: list[GoldRisk] = Field(default_factory=list)
    must_not: list[MustNot] = Field(default_factory=list)


# --- The evaluation ---------------------------------------------------------------------

class EntryResult(BaseModel):
    kind: Literal["figure", "guidance", "risk"]
    anchor: str
    expected: str
    outcome: str
    item_id: str | None = None
    wrong_fields: list[str] = Field(default_factory=list)
    gate_reasons: list[str] = Field(default_factory=list)  # why the item was held back, if it was
    qualifier_captured: bool | None = None  # guidance with a qualifier_anchor only


class MustNotViolation(BaseModel):
    kind: str
    value: str
    reason: str
    item_id: str
    item_value: str


class UnlabelledExtra(BaseModel):
    item_id: str
    kind: str
    description: str


class Headline(BaseModel):
    correct_items: int  # verified items matching the key with every field right
    matched_items: int  # verified items matching the key
    coverage: dict[str, list[int]]  # kind -> [entries scored "correct", entries in the key]
    qualifiers_captured: int
    qualifiers_total: int
    violations: int
    false_accepts: int  # verified, but a field is wrong
    false_rejects: int  # held back by the gate, although every field was right


class Evaluation(BaseModel):
    headline: Headline
    entries: list[EntryResult]
    must_not_violations: list[MustNotViolation]
    unlabelled_extras: list[UnlabelledExtra]
