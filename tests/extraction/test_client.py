import json

import pytest

from extraction import Extraction, LlmError, NvidiaProvider
from extraction.client import strip_reasoning
from tests.extraction.fakes import VALID, FakeClient, api_error, response, settings

ONE_FIGURE = {**VALID, "figures": [{
    "metric": "Revenue", "value": "$5 million", "period": "Q1", "is_comparison": False,
    "basis": "not stated", "speaker": "Jane Doe", "quote": "Revenue was $5 million.", "context_quotes": [],
}]}


def provider(tmp_path, *items, **setting_overrides):
    client = FakeClient(*items)
    return NvidiaProvider(settings(tmp_path, **setting_overrides), cache_mode="refresh", client=client), client


def complete(p, name="prepared"):
    return p.complete(name, "SYSTEM", "USER", Extraction)


# --- parsing and repair ---------------------------------------------------------

def test_valid_json_parses(tmp_path):
    p, client = provider(tmp_path, response(json.dumps(ONE_FIGURE)))
    result, replayed = complete(p)
    assert result.figures[0].value == "$5 million" and replayed is False
    assert len(client.requests) == 1
    assert p.usage.calls == 1 and p.usage.prompt_tokens == 100 and p.usage.completion_tokens == 20


def test_json_fences_parse(tmp_path):
    p, _ = provider(tmp_path, response("```json\n" + json.dumps(ONE_FIGURE) + "\n```"))
    assert complete(p)[0].figures[0].metric == "Revenue"


def test_invalid_then_valid_makes_one_repair_call_with_the_error(tmp_path):
    bad = {**ONE_FIGURE, "figures": [{**ONE_FIGURE["figures"][0], "basis": "IFRS"}]}
    p, client = provider(tmp_path, response(json.dumps(bad)), response(json.dumps(ONE_FIGURE)))
    result, _ = complete(p)
    assert result.figures[0].basis == "not stated"
    assert len(client.requests) == 2
    repair = client.requests[1]["messages"]
    assert repair[-2] == {"role": "assistant", "content": json.dumps(bad)}
    assert repair[-1]["content"].startswith("Your output failed validation:")
    assert "basis" in repair[-1]["content"] and repair[-1]["content"].endswith("Return corrected JSON only.")


def test_invalid_twice_raises(tmp_path):
    p, client = provider(tmp_path, response("not json"), response('{"figures": []}'))
    with pytest.raises(LlmError, match="after one repair attempt"):
        complete(p)
    assert len(client.requests) == 2


@pytest.mark.parametrize("bad, message", [
    (response(finish_reason="length"), "cut off"),
    (response(finish_reason="content_filter"), "content filter"),
    (response(refusal="I can't help with that."), "refused"),
    (response(content=""), "empty content"),
    (response(content=None), "empty content"),
    (response(choices=False), "no choices"),
])
def test_unusable_output_raises_without_repair(tmp_path, bad, message):
    p, client = provider(tmp_path, bad)
    with pytest.raises(LlmError, match=message):
        complete(p)
    assert len(client.requests) == 1


def test_other_api_errors_raise_without_fallback(tmp_path):
    p, client = provider(tmp_path, api_error("model not found", status=400))
    with pytest.raises(LlmError, match="400"):
        complete(p)
    assert len(client.requests) == 1


# --- structured-output fallback chain -------------------------------------------

def test_json_schema_is_tried_first(tmp_path):
    p, client = provider(tmp_path, response())
    complete(p)
    fmt = client.requests[0]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"] == Extraction.model_json_schema()
    assert client.requests[0]["messages"][0]["content"] == "SYSTEM"  # schema not in the prompt
    assert p.structured_output_mode == "json_schema"


def test_rejected_json_schema_falls_back_to_json_object_and_is_remembered(tmp_path):
    p, client = provider(
        tmp_path,
        api_error("response_format type json_schema is not supported for this model"),
        response(json.dumps(ONE_FIGURE)),
        response(),  # the next call
    )
    assert complete(p)[0].figures[0].value == "$5 million"
    level2 = client.requests[1]
    assert level2["response_format"] == {"type": "json_object"}
    assert level2["messages"][0]["content"].startswith("SYSTEM")
    assert '"figures"' in level2["messages"][0]["content"]  # schema appended to the system prompt
    assert p.structured_output_mode == "json_object"

    complete(p, name="qa")  # later calls start at the level that worked
    assert client.requests[2]["response_format"] == {"type": "json_object"}
    assert len(client.requests) == 3


def test_rejected_json_schema_and_json_object_fall_back_to_prompt_only(tmp_path):
    p, client = provider(
        tmp_path,
        api_error("Invalid response_format: json_schema not supported", status=422),
        api_error("response_format json_object is not supported"),
        response(json.dumps(ONE_FIGURE)),
    )
    assert complete(p)[0].figures[0].value == "$5 million"
    level3 = client.requests[2]
    assert "response_format" not in level3
    assert '"figures"' in level3["messages"][0]["content"]
    assert p.structured_output_mode == "prompt_only"


def test_repair_still_applies_after_fallback(tmp_path):
    p, client = provider(
        tmp_path,
        api_error("json_schema not supported"),
        response("not json"),
        response(json.dumps(ONE_FIGURE)),
    )
    assert complete(p)[0].figures[0].value == "$5 million"
    assert [r["response_format"]["type"] for r in client.requests] == ["json_schema", "json_object", "json_object"]


def test_reasoning_effort_sent_only_when_set(tmp_path):
    p, client = provider(tmp_path, response())
    complete(p)
    assert "reasoning_effort" not in client.requests[0]
    p, client = provider(tmp_path, response(), reasoning_effort="low")
    complete(p)
    assert client.requests[0]["reasoning_effort"] == "low"


# --- <think> blocks ---------------------------------------------------------------

def test_think_blocks_are_stripped_before_parsing(tmp_path):
    content = "<think>The user wants figures. Revenue is $5 million.</think>\n" + json.dumps(ONE_FIGURE)
    p, _ = provider(tmp_path, response(content))
    assert complete(p)[0].figures[0].value == "$5 million"


def test_content_that_is_only_reasoning_raises(tmp_path):
    p, client = provider(tmp_path, response("<think>Still thinking about the answer</think>"))
    with pytest.raises(LlmError, match="empty content"):
        complete(p)
    assert len(client.requests) == 1


@pytest.mark.parametrize("content, expected", [
    ("<think>a</think>{}", "{}"),
    ("<THINK>a\nb</THINK> {} ", "{}"),
    ("<think>a</think><think>b</think>{}", "{}"),
    ("reasoning without an opening tag</think>{}", "{}"),
    ("{} <think>unfinished", "{}"),
    ("<think>unfinished", ""),
])
def test_strip_reasoning(content, expected):
    assert strip_reasoning(content) == expected
