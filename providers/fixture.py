"""Replays saved LLM outputs from a JSON file instead of calling the API."""

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from providers.base import LlmError
from schema.extraction import Usage


class FixtureProvider:
    """Replays saved answers from a JSON file instead of calling an API. Used in tests.

    The file looks like {"model": "...", "calls": {"prepared": {...}, "qa": {...}}}.
    Saved answers are validated against the schema, just like live ones.
    """

    def __init__(self, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.model = data["model"]
        self.calls: dict = data["calls"]
        self.fallback_models: list[str] = []
        self.last_model: str | None = None
        self.last_mode: str | None = None
        self.usage = Usage()

    def complete(
        self, name: str, system: str, user: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, bool]:
        if name not in self.calls:
            raise LlmError(f"Fixture has no output for '{name}'.")
        try:
            result = schema.model_validate(self.calls[name])
        except ValidationError as error:
            raise LlmError(f"Fixture output for '{name}' failed validation: {error}") from error
        self.usage.replayed_calls += 1
        self.last_model = self.model
        self.last_mode = "fixture"
        return result, True
