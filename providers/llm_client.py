"""Talks to one model through an OpenAI-compatible chat API, and returns the text it answers."""

import time
from collections.abc import Callable
from typing import Any

import openai

from config import Endpoint, Settings
from constants.llm import (
    RETRY_PAUSE_SECONDS,
    STRUCTURED_OUTPUT_MODES,
    TRANSIENT_RETRIES,
)
from providers.base import LlmError
from schema.extraction import Usage
from utils.llm import is_response_format_error, schema_instructions, strip_reasoning


class LlmClient:
    """Sends chat requests to one model and returns the text of its answer.

    Not every model supports every way of asking for JSON. The client tries the
    strictest mode first (see STRUCTURED_OUTPUT_MODES), steps down if the server
    rejects it, and remembers the mode that worked for the rest of the run.

    A timeout is not retried (the provider moves on to the next model). Rate limits,
    server errors and dropped connections are retried TRANSIENT_RETRIES times.
    """

    def __init__(
        self,
        endpoint: Endpoint,
        settings: Settings,
        usage: Usage,
        openai_client: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.endpoint = endpoint
        self.settings = settings
        self.usage = usage  # shared with the provider, and updated after every answer
        self.mode_index = 0
        self._openai_client = openai_client  # tests pass a fake; otherwise made on first use
        self._sleep = sleep  # tests pass a no-op, so retries don't really wait

    def chat(
        self, system: str, messages: list[dict], schema_name: str, schema_json: dict
    ) -> tuple[str, str]:
        """Send one chat request. Returns (answer text, structured-output mode used).
        Raises LlmError if the request fails or the answer can't be used."""
        retries = 0
        while True:
            mode = STRUCTURED_OUTPUT_MODES[self.mode_index]
            request = self._build_request(mode, system, messages, schema_name, schema_json)
            try:
                response = self._client().chat.completions.create(**request)
            except openai.APITimeoutError as error:
                raise LlmError(f"timed out after {self.settings.timeout:.0f}s") from error
            except openai.APIStatusError as error:
                can_step_down = self.mode_index < len(STRUCTURED_OUTPUT_MODES) - 1
                if can_step_down and is_response_format_error(error):
                    self.mode_index += 1
                    continue
                if _is_transient(error) and retries < TRANSIENT_RETRIES:
                    retries += 1
                    self._sleep(RETRY_PAUSE_SECONDS * retries)
                    continue
                raise LlmError(f"API error {error.status_code}: {error.message}") from error
            except openai.APIConnectionError as error:
                if retries < TRANSIENT_RETRIES:
                    retries += 1
                    self._sleep(RETRY_PAUSE_SECONDS * retries)
                    continue
                raise LlmError(f"API request failed: {error}") from error
            except openai.APIError as error:
                raise LlmError(f"API request failed: {error}") from error
            return self._answer_text(response), mode

    def _client(self) -> Any:
        # Made on first use, so a cache-only run never needs an API key.
        if self._openai_client is None:
            self._openai_client = openai.OpenAI(
                base_url=self.endpoint.base_url,
                api_key=self.endpoint.api_key,
                timeout=self.settings.timeout,
                max_retries=0,  # retries are decided in chat(), so timeouts aren't retried
            )
        return self._openai_client

    def _build_request(
        self, mode: str, system: str, messages: list[dict], schema_name: str, schema_json: dict
    ) -> dict:
        if mode != "json_schema":
            system += schema_instructions(schema_json)

        request = {
            "model": self.endpoint.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
        }
        if mode == "json_schema":
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema_json, "strict": True},
            }
        if mode == "json_object":
            request["response_format"] = {"type": "json_object"}
        if self.settings.reasoning_effort:
            request["reasoning_effort"] = self.settings.reasoning_effort
        return request

    def _answer_text(self, response: Any) -> str:
        """The usable text of a response. Raises LlmError (with no retry) if there is none."""
        self.usage.calls += 1
        if response.usage:
            self.usage.prompt_tokens += response.usage.prompt_tokens or 0
            self.usage.completion_tokens += response.usage.completion_tokens or 0

        if not response.choices:
            raise LlmError("Model returned no choices.")
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise LlmError("Output was cut off (finish_reason=length).")
        if choice.finish_reason == "content_filter":
            raise LlmError("Output was blocked by a content filter (finish_reason=content_filter).")
        if choice.message.refusal:
            raise LlmError(f"Model refused: {choice.message.refusal}")

        text = strip_reasoning(choice.message.content or "")
        if not text:
            raise LlmError("Model returned empty content (after removing <think> blocks).")
        return text


def _is_transient(error: openai.APIStatusError) -> bool:
    """A rate limit or a server-side error: worth trying again after a pause."""
    return error.status_code == 429 or error.status_code >= 500
