"""LLM providers: the live NVIDIA (OpenAI-compatible) API, and a fixture replayer.

A provider returns exactly what the model said, validated against the schema. It
checks nothing about the transcript itself; that is Stage 3's job.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Protocol

import openai
from pydantic import BaseModel, ValidationError

from .cache import CacheMode, DiskCache, cache_key
from .config import PROMPT_VERSION, Settings
from .models import Usage

# Ways of asking for structured output, most to least strict. Not every NVIDIA-hosted
# model supports json_schema, so the provider steps down on a 400/422 about it.
STRUCTURED_OUTPUT_MODES = ("json_schema", "json_object", "prompt_only")

# Words in a 400/422 error body that show the server rejected response_format.
_RESPONSE_FORMAT_ERROR_WORDS = ("response_format", "json_schema", "json_object", "guided", "schema")

# ```json ... ``` (or plain ```) fences around the whole output.
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S | re.I)
# A complete <think>...</think> reasoning block.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S | re.I)


class LlmError(Exception):
    """The model's output can't be used. The section is marked failed."""


class Provider(Protocol):
    model: str
    usage: Usage
    structured_output_mode: str | None

    def complete(
        self, name: str, system: str, user: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, bool]:
        """Return (validated output, replayed)."""
        ...


def strip_reasoning(content: str) -> str:
    """Remove <think>...</think> blocks some models put in their content.

    Also handles a lone "</think>" (the opening tag was part of the prompt template:
    keep what follows it) and an unclosed "<think>" (the output was all reasoning:
    drop from the tag on).
    """
    text = _THINK_BLOCK.sub("", content)
    if (i := text.lower().rfind("</think>")) != -1:
        text = text[i + len("</think>"):]
    if (i := text.lower().find("<think>")) != -1:
        text = text[:i]
    return text.strip()


def _parse(content: str, schema: type[BaseModel]) -> BaseModel:
    """Parse and validate model output. Raises ValueError with a readable message."""
    if m := _FENCE.match(content):
        content = m.group(1)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"not valid JSON ({e})") from e
    try:
        return schema.model_validate(data)
    except ValidationError as e:
        raise ValueError(str(e)) from e


def _schema_instructions(schema_json: dict) -> str:
    return "\n\nReturn a JSON object that matches this JSON schema:\n" + json.dumps(schema_json)


def _is_response_format_error(error: openai.APIStatusError) -> bool:
    if error.status_code not in (400, 422):
        return False
    text = f"{error.message} {json.dumps(error.body, default=str)}".lower()
    return any(word in text for word in _RESPONSE_FORMAT_ERROR_WORDS)


class NvidiaProvider:
    """Calls an OpenAI-compatible chat API (NVIDIA by default), with a disk cache.

    `client` can be injected for tests; otherwise an openai.OpenAI client is built
    from settings. Transport retries (429, 5xx, timeouts) are left to the SDK and
    are separate from the single schema-repair attempt.
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
        self.cache_mode = cache_mode
        self.cache = cache or DiskCache(settings.cache_dir)
        self._client = client
        self._mode_index = 0  # remembered for the rest of the run once a level works
        self.structured_output_mode: str | None = None
        self.usage = Usage()

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = openai.OpenAI(
                base_url=self.settings.base_url,
                api_key=self.settings.api_key,
                timeout=self.settings.timeout,
                max_retries=2,
            )
        return self._client

    def complete(
        self, name: str, system: str, user: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, bool]:
        schema_json = schema.model_json_schema()
        key = cache_key(
            base_url=self.settings.base_url,
            model=self.settings.model,
            reasoning_effort=self.settings.reasoning_effort,
            prompt_version=PROMPT_VERSION,
            name=name,
            system=system,
            user=user,
            schema=schema_json,
        )
        if self.cache_mode in ("auto", "cached"):
            entry = self.cache.get(key)
            if entry is not None:
                self.usage.replayed_calls += 1
                self.structured_output_mode = self.structured_output_mode or entry["structured_output_mode"]
                return schema.model_validate(entry["parsed"]), True
            if self.cache_mode == "cached":
                raise LlmError(f"No cached response for '{name}' and cache mode is 'cached'.")

        conversation = [{"role": "user", "content": user}]
        raw = self._chat(system, conversation, schema.__name__, schema_json)
        try:
            result = _parse(raw, schema)
        except ValueError as first:
            # One repair attempt: show the model its output and what was wrong with it.
            conversation += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"Your output failed validation: {first}. Return corrected JSON only."},
            ]
            raw = self._chat(system, conversation, schema.__name__, schema_json)
            try:
                result = _parse(raw, schema)
            except ValueError as second:
                raise LlmError(f"Output failed validation after one repair attempt: {second}") from second

        self.cache.put(
            key,
            raw=raw,
            parsed=result.model_dump(mode="json"),
            structured_output_mode=self.structured_output_mode,
        )
        return result, False

    def _request_args(self, mode: str, system: str, conversation: list[dict], schema_name: str, schema_json: dict) -> dict:
        if mode != "json_schema":
            system += _schema_instructions(schema_json)
        args: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [{"role": "system", "content": system}, *conversation],
            "temperature": self.settings.temperature,
        }
        if mode == "json_schema":
            args["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema_json, "strict": True},
            }
        elif mode == "json_object":
            args["response_format"] = {"type": "json_object"}
        if self.settings.reasoning_effort:
            args["reasoning_effort"] = self.settings.reasoning_effort
        return args

    def _chat(self, system: str, conversation: list[dict], schema_name: str, schema_json: dict) -> str:
        """One chat call, stepping down the structured-output modes if the server rejects one."""
        while True:
            mode = STRUCTURED_OUTPUT_MODES[self._mode_index]
            try:
                response = self.client.chat.completions.create(
                    **self._request_args(mode, system, conversation, schema_name, schema_json)
                )
            except openai.APIStatusError as e:
                if self._mode_index < len(STRUCTURED_OUTPUT_MODES) - 1 and _is_response_format_error(e):
                    self._mode_index += 1
                    continue
                raise LlmError(f"API error {e.status_code}: {e.message}") from e
            except openai.APIError as e:
                raise LlmError(f"API request failed: {e}") from e
            self.structured_output_mode = mode
            return self._content(response)

    def _content(self, response: Any) -> str:
        """The usable text of a response. Raises LlmError, with no retry, if there is none."""
        self.usage.calls += 1
        if usage := getattr(response, "usage", None):
            self.usage.prompt_tokens += usage.prompt_tokens or 0
            self.usage.completion_tokens += usage.completion_tokens or 0
        if not response.choices:
            raise LlmError("Model returned no choices.")
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise LlmError("Output was cut off (finish_reason=length).")
        if choice.finish_reason == "content_filter":
            raise LlmError("Output was blocked by a content filter (finish_reason=content_filter).")
        if refusal := getattr(choice.message, "refusal", None):
            raise LlmError(f"Model refused: {refusal}")
        content = strip_reasoning(choice.message.content or "")
        if not content:
            raise LlmError("Model returned empty content (after removing <think> blocks).")
        return content


class FixtureProvider:
    """Replays hand-written or saved outputs from a JSON file:
    {"model": "...", "calls": {"prepared": {...}, "qa": {...}}}.
    Outputs go through the same pydantic validation as live ones.
    """

    def __init__(self, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.model = data["model"]
        self.calls: dict = data["calls"]
        self.structured_output_mode: str | None = "fixture"
        self.usage = Usage()

    def complete(
        self, name: str, system: str, user: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, bool]:
        if name not in self.calls:
            raise LlmError(f"Fixture has no output for '{name}'.")
        try:
            result = schema.model_validate(self.calls[name])
        except ValidationError as e:
            raise LlmError(f"Fixture output for '{name}' failed validation: {e}") from e
        self.usage.replayed_calls += 1
        return result, True
