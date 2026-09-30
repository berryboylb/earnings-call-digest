"""What every LLM provider shares: the interface and the error it raises."""

from typing import Protocol

from pydantic import BaseModel

from schema.extraction import Usage


class LlmError(Exception):
    """The model's output can't be used. The section is marked failed."""


class Provider(Protocol):
    model: str                  # the primary model
    fallback_models: list[str]
    usage: Usage
    last_model: str | None      # which model produced the last result
    last_mode: str | None       # how structured output was requested for it

    def complete(
        self, name: str, system: str, user: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, bool]:
        """Return (validated output, replayed)."""
        ...
