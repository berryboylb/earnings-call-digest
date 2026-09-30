"""The NVIDIA provider: gets a validated answer from the models set in .env.

It returns exactly what the model said; checking it against the transcript is Stage 3.
"""

from typing import Any

from pydantic import BaseModel

from config import Settings
from constants.prompts import PROMPT_VERSION, REPAIR_INSTRUCTIONS
from providers.base import LlmError
from providers.llm_client import LlmClient
from schema.extraction import Usage
from utils.cache import CacheMode, DiskCache, cache_key
from utils.llm import parse_model_output


class NvidiaProvider:
    """Gets a validated answer for each request, in this order:

    1. A cached answer, if there is one (unless cache_mode is "refresh").
    2. The main model (LLM_MODEL), with one repair attempt if its answer is invalid.
    3. Each fallback model (LLM_MODEL_FALLBACK) in turn, if the one before failed.

    `last_model` and `last_mode` record which model answered, and how.
    Tests pass a fake `client`, which then stands in for every model's API.
    """

    def __init__(
        self,
        settings: Settings,
        cache_mode: CacheMode = "auto",
        client: Any = None,
        cache: DiskCache | None = None,
    ):
        self.settings = settings
        self.model = settings.model
        self.fallback_models = [endpoint.model for endpoint in settings.fallbacks]
        self.cache_mode = cache_mode
        self.cache = cache or DiskCache(settings.cache_dir)
        self.usage = Usage()
        self.last_model = None
        self.last_mode = None
        self.clients = [
            LlmClient(endpoint, settings, self.usage, client) for endpoint in settings.endpoints
        ]

    def complete(
        self, name: str, system: str, user: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, bool]:
        """Return (validated answer, True if it came from the cache). Raises LlmError if every model fails."""
        schema_json = schema.model_json_schema()
        cache_keys = [
            self._cache_key(client, name, system, user, schema_json) for client in self.clients
        ]

        if self.cache_mode != "refresh":
            cached_answer = self._cached_answer(cache_keys, schema)
            if cached_answer is not None:
                return cached_answer, True
            if self.cache_mode == "cached":
                raise LlmError(f"No cached response for '{name}' and cache mode is 'cached'.")

        errors = []  # (model, what went wrong)
        for client, key in zip(self.clients, cache_keys):
            try:
                answer, raw_text, mode = self._ask(client, system, user, schema, schema_json)
            except LlmError as error:
                errors.append((client.endpoint.model, str(error)))
                continue
            self.cache.put(key, raw=raw_text, parsed=answer.model_dump(mode="json"), structured_output_mode=mode)
            self.last_model = client.endpoint.model
            self.last_mode = mode
            return answer, False

        if len(errors) == 1:
            _, message = errors[0]
            raise LlmError(message)
        summary = " | ".join(f"{model}: {message}" for model, message in errors)
        raise LlmError(f"All models failed. {summary}")

    def _cached_answer(self, cache_keys: list[str], schema: type[BaseModel]) -> BaseModel | None:
        """A saved answer from any of the models (including a fallback on an earlier run), or None."""
        for client, key in zip(self.clients, cache_keys):
            entry = self.cache.get(key)
            if entry is not None:
                self.usage.replayed_calls += 1
                self.last_model = client.endpoint.model
                self.last_mode = entry["structured_output_mode"]
                return schema.model_validate(entry["parsed"])
        return None

    def _ask(
        self, client: LlmClient, system: str, user: str, schema: type[BaseModel], schema_json: dict
    ) -> tuple[BaseModel, str, str]:
        """Ask one model, with one repair attempt. Returns (answer, raw text, structured-output mode)."""
        messages = [{"role": "user", "content": user}]
        raw_text, mode = client.chat(system, messages, schema.__name__, schema_json)
        try:
            return parse_model_output(raw_text, schema), raw_text, mode
        except ValueError as first_error:
            # Show the model its own answer and what was wrong with it, and ask once more.
            messages.append({"role": "assistant", "content": raw_text})
            messages.append({"role": "user", "content": REPAIR_INSTRUCTIONS.format(errors=first_error)})

        raw_text, mode = client.chat(system, messages, schema.__name__, schema_json)
        try:
            return parse_model_output(raw_text, schema), raw_text, mode
        except ValueError as second_error:
            raise LlmError(f"Output failed validation after one repair attempt: {second_error}") from second_error

    def _cache_key(self, client: LlmClient, name: str, system: str, user: str, schema_json: dict) -> str:
        return cache_key(
            base_url=client.endpoint.base_url,
            model=client.endpoint.model,
            reasoning_effort=self.settings.reasoning_effort,
            prompt_version=PROMPT_VERSION,
            name=name,
            system=system,
            user=user,
            schema=schema_json,
        )
