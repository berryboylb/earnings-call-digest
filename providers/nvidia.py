"""The NVIDIA provider: gets a validated answer from the models set in .env.

It returns exactly what the model said; checking it against the transcript is Stage 3.
"""

import time
from collections.abc import Callable
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

    `last_model` and `last_mode` record which model answered, and how. While it waits for
    a model it prints progress lines, so a long wait never looks like a hang.
    Tests pass a fake `client`, which then stands in for every model's API.
    """

    def __init__(
        self,
        settings: Settings,
        cache_mode: CacheMode = "auto",
        client: Any = None,
        cache: DiskCache | None = None,
        log: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings
        self.model = settings.model
        self.fallback_models = [endpoint.model for endpoint in settings.fallbacks]
        self.cache_mode = cache_mode
        self.cache = cache or DiskCache(settings.cache_dir)
        self.usage = Usage()
        self.last_model = None
        self.last_mode = None
        self.last_failures = []
        self.log = log or _print_now
        self.clients = [
            LlmClient(endpoint, settings, self.usage, client, sleep) for endpoint in settings.endpoints
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
        for i, (client, key) in enumerate(zip(self.clients, cache_keys)):
            model = client.endpoint.model
            self.log(f"  [{name}] asking {model} ...")
            started = time.monotonic()
            try:
                answer, raw_text, mode = self._ask(client, system, user, schema, schema_json)
            except LlmError as error:
                errors.append((model, str(error)))
                next_model = self.clients[i + 1].endpoint.model if i + 1 < len(self.clients) else None
                then = f"; trying {next_model}" if next_model else ""
                self.log(f"  [{name}] {model} failed after {_duration(started)}: {error}{then}")
                continue
            self.log(f"  [{name}] answered in {_duration(started)}")
            self.cache.put(key, raw=raw_text, parsed=answer.model_dump(mode="json"), structured_output_mode=mode)
            self.last_model = client.endpoint.model
            self.last_mode = mode
            self.last_failures = [f"{model}: {message}" for model, message in errors]
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
                self.last_failures = []
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


def _print_now(message: str) -> None:
    print(message, flush=True)


def _duration(started: float) -> str:
    """Time since `started`, e.g. "45s" or "3m12s"."""
    seconds = int(time.monotonic() - started)
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}m{seconds % 60:02d}s"
