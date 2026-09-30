"""A fake OpenAI-style client and helpers for building its responses. No network."""

import json
from types import SimpleNamespace

import openai

from extraction import Settings

VALID = {"figures": [], "guidance": [], "risks": [], "qa_topics": []}


def settings(tmp_path, **overrides):
    values = dict(base_url="https://test.invalid/v1", api_key="test-key", model="test/model",
                  cache_dir=tmp_path / "cache")
    return Settings(**{**values, **overrides})


def response(content=json.dumps(VALID), finish_reason="stop", refusal=None, choices=True):
    message = SimpleNamespace(content=content, refusal=refusal)
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish_reason, message=message)] if choices else [],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
    )


def api_error(message, status=400):
    """An SDK error as the server would send it, e.g. a 400 rejecting response_format."""
    cls = {400: openai.BadRequestError, 422: openai.UnprocessableEntityError}[status]
    stub = SimpleNamespace(status_code=status, headers={}, request=SimpleNamespace(method="POST", url="x"))
    return cls(f"Error code: {status} - {message}", response=stub, body={"error": {"message": message}})


class FakeClient:
    """Returns (or raises) the given items in order and records every request."""

    def __init__(self, *items):
        self.items = list(items)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if not self.items:
            raise AssertionError("unexpected extra API call")
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
