from pathlib import Path
from types import SimpleNamespace

import openai
import pytest

from config import Endpoint
from extraction.extractor import run_extraction
from parsing.parser import parse_file
from providers.base import LlmError
from providers.nvidia import NvidiaProvider
from schema.extraction import Extraction
from tests.providers.fakes import VALID, FakeClient, api_error, response, settings

FALLBACK = Endpoint("fallback/model", "https://fallback.invalid/v1", "fallback-key")


def rate_limited():
    stub = SimpleNamespace(status_code=429, headers={}, request=SimpleNamespace(method="POST", url="x"))
    return openai.RateLimitError("Error code: 429 - rate limit exceeded", response=stub, body=None)


def provider(tmp_path, *items, fallbacks=(FALLBACK,), cache_mode="auto"):
    client = FakeClient(*items)
    return NvidiaProvider(settings(tmp_path, fallbacks=fallbacks), cache_mode=cache_mode, client=client), client


def complete(p, name="prepared"):
    return p.complete(name, "SYSTEM", "USER", Extraction)


def test_rate_limit_on_primary_falls_back(tmp_path):
    p, client = provider(tmp_path, rate_limited(), response())
    result, replayed = complete(p)
    assert result == Extraction(**VALID) and replayed is False
    assert [request["model"] for request in client.requests] == ["test/model", "fallback/model"]
    assert p.last_model == "fallback/model"


@pytest.mark.parametrize("primary_failure", [
    api_error("internal error", status=400),                       # not about response_format
    response(finish_reason="length"),                              # unusable output
    response("<think>only reasoning</think>"),                     # empty after stripping
])
def test_other_primary_failures_fall_back(tmp_path, primary_failure):
    p, client = provider(tmp_path, primary_failure, response())
    complete(p)
    assert client.requests[-1]["model"] == "fallback/model"
    assert p.last_model == "fallback/model"


def test_invalid_output_twice_on_primary_falls_back(tmp_path):
    p, client = provider(tmp_path, response("nope"), response("still nope"), response())
    complete(p)
    assert [request["model"] for request in client.requests] == ["test/model", "test/model", "fallback/model"]


def test_primary_success_never_calls_fallback(tmp_path):
    p, client = provider(tmp_path, response())
    complete(p)
    assert [request["model"] for request in client.requests] == ["test/model"]
    assert p.last_model == "test/model"


def test_all_models_failing_raises_with_every_error(tmp_path):
    second = Endpoint("second/model", "https://fallback.invalid/v1", "fallback-key")
    p, _ = provider(tmp_path, rate_limited(), response(content=""), response(finish_reason="length"),
                    fallbacks=(FALLBACK, second))
    with pytest.raises(LlmError) as e:
        complete(p)
    message = str(e.value)
    assert message.startswith("All models failed.")
    assert "test/model: API error 429" in message
    assert "fallback/model: Model returned empty content" in message
    assert "second/model: Output was cut off" in message


def test_each_model_keeps_its_own_structured_output_level(tmp_path):
    p, client = provider(
        tmp_path,
        api_error("json_schema is not supported"), rate_limited(),  # primary: steps down, then 429
        response(),                                                  # fallback starts at json_schema
    )
    complete(p)
    assert [(request["model"], request.get("response_format", {}).get("type")) for request in client.requests] == [
        ("test/model", "json_schema"), ("test/model", "json_object"), ("fallback/model", "json_schema"),
    ]
    assert p.last_mode == "json_schema"


def test_fallback_answer_is_cached_under_its_own_key_and_replayed(tmp_path):
    p, client = provider(tmp_path, rate_limited(), response())
    complete(p)
    replayer = NvidiaProvider(settings(tmp_path, fallbacks=(FALLBACK,)), cache_mode="cached", client=FakeClient())
    _, replayed = complete(replayer)
    assert replayed is True and replayer.last_model == "fallback/model"
    assert (tmp_path / "cache").exists() and len(list((tmp_path / "cache").iterdir())) == 1


def test_section_records_which_model_answered(tmp_path):
    parsed = parse_file(Path(__file__).parents[2] / "data" / "meridian.txt")
    p, _ = provider(tmp_path, response(), rate_limited(), response())  # prepared: primary; qa: fallback
    run = run_extraction(parsed, p)
    assert [(section.name, section.status, section.model) for section in run.sections] == [
        ("prepared", "ok", "test/model"), ("qa", "ok", "fallback/model"),
    ]
    assert run.model == "test/model" and run.fallback_models == ["fallback/model"]
    assert run.structured_output_mode == "json_schema"
