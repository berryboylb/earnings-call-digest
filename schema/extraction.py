"""The shape of what the LLM must return, and of the results of a run.

The models the LLM fills in forbid extra fields and make every field required,
because strict JSON-schema mode needs every field listed as required.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from constants.llm import MAX_CONTEXT_QUOTES


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- What the LLM returns ------------------------------------------------------

class Figure(_Strict):
    metric: str
    value: str
    period: str
    is_comparison: bool
    basis: Literal["GAAP", "non-GAAP", "not stated"]
    speaker: str
    quote: str
    context_quotes: list[str] = Field(max_length=MAX_CONTEXT_QUOTES)


class Guidance(_Strict):
    metric: str
    range: str
    period: str
    direction: Literal["raised", "lowered", "reaffirmed", "initiated", "not stated"]
    speaker: str
    quote: str
    context_quotes: list[str] = Field(max_length=MAX_CONTEXT_QUOTES)


class Risk(_Strict):
    theme: str
    hedging_phrase: str
    speaker: str
    quote: str


class QaTopic(_Strict):
    topic: str
    asked_by: str
    answer_quality: Literal["direct", "partial", "deflected"]
    speaker: str
    quote: str


class Extraction(_Strict):
    figures: list[Figure]
    guidance: list[Guidance]
    risks: list[Risk]
    qa_topics: list[QaTopic]


# --- Results of a run ----------------------------------------------------------

SectionName = Literal["prepared", "qa"]


class Usage(BaseModel):
    calls: int = 0           # API responses received (including repair calls)
    replayed_calls: int = 0  # answered from the cache or a fixture instead
    prompt_tokens: int = 0
    completion_tokens: int = 0


class SectionResult(BaseModel):
    name: SectionName
    status: Literal["ok", "failed", "empty_input"]
    extraction: Extraction | None
    error: str | None
    replayed: bool
    # Which model produced the extraction (the primary or a fallback), and how structured
    # output was requested: "json_schema", "json_object", "prompt_only" or "fixture".
    model: str | None = None
    structured_output_mode: str | None = None


class ExtractionRun(BaseModel):
    sections: list[SectionResult]
    model: str  # the primary model
    fallback_models: list[str]
    prompt_version: str
    # The structured-output mode(s) the sections used, comma-separated; None if no section got output.
    structured_output_mode: str | None
    usage: Usage
