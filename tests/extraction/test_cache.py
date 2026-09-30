import pytest

from extraction import Extraction, LlmError, NvidiaProvider
from extraction.cache import cache_key
from tests.extraction.fakes import FakeClient, response, settings

KEY_ARGS = dict(base_url="https://integrate.api.nvidia.com/v1", model="m", reasoning_effort="",
                prompt_version="v1", name="prepared", system="S", user="U",
                schema=Extraction.model_json_schema())


def test_identical_second_call_is_replayed_without_calling_the_client(tmp_path):
    client = FakeClient(response())  # only one response: a second API call would fail the test
    p = NvidiaProvider(settings(tmp_path), cache_mode="auto", client=client)
    first, replayed_first = p.complete("prepared", "S", "U", Extraction)
    second, replayed_second = p.complete("prepared", "S", "U", Extraction)
    assert (replayed_first, replayed_second) == (False, True)
    assert second == first
    assert len(client.requests) == 1
    assert (p.usage.calls, p.usage.replayed_calls) == (1, 1)


def test_replay_works_across_provider_instances_and_keeps_the_mode(tmp_path):
    NvidiaProvider(settings(tmp_path), client=FakeClient(response())).complete("qa", "S", "U", Extraction)
    replayer = NvidiaProvider(settings(tmp_path), cache_mode="cached", client=FakeClient())
    assert replayer.complete("qa", "S", "U", Extraction)[1] is True
    assert replayer.structured_output_mode == "json_schema"


@pytest.mark.parametrize("field, value", [
    ("prompt_version", "v2"),
    ("model", "other/model"),
    ("schema", {"type": "object"}),
    ("base_url", "https://openrouter.ai/api/v1"),
    ("reasoning_effort", "high"),
    ("user", "U2"),
])
def test_changing_an_input_changes_the_key(field, value):
    assert cache_key(**KEY_ARGS) != cache_key(**{**KEY_ARGS, field: value})


def test_cached_mode_with_no_entry_raises(tmp_path):
    client = FakeClient()
    p = NvidiaProvider(settings(tmp_path), cache_mode="cached", client=client)
    with pytest.raises(LlmError, match="No cached response"):
        p.complete("prepared", "S", "U", Extraction)
    assert client.requests == []


def test_refresh_mode_calls_again_and_overwrites(tmp_path):
    client = FakeClient(response(), response())
    p = NvidiaProvider(settings(tmp_path), cache_mode="refresh", client=client)
    p.complete("prepared", "S", "U", Extraction)
    assert p.complete("prepared", "S", "U", Extraction)[1] is False
    assert len(client.requests) == 2
