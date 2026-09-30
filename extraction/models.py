"""Pydantic models: what the LLM must return, and the results of a run.

The LLM-facing models forbid extra fields and make every field required, because
strict JSON-schema mode needs every property listed as required.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    context_quotes: list[str] = Field(max_length=2)


class Guidance(_Strict):
    metric: str
    range: str
    period: str
    direction: Literal["raised", "lowered", "reaffirmed", "initiated", "not stated"]
    speaker: str
    quote: str
    context_quotes: list[str] = Field(max_length=2)


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


class ExtractionRun(BaseModel):
    sections: list[SectionResult]
    model: str
    prompt_version: str
    # How structured output was requested: "json_schema", "json_object", "prompt_only",
    # or "fixture". None if no call was made.
    structured_output_mode: str | None
    usage: Usage
