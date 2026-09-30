import pytest

from config import DEFAULT_BASE_URL, ConfigError, Endpoint, load_settings

VARS = ["LLM_MODEL", "LLM_MODEL_FALLBACK", "NVIDIA_API_KEY", "LLM_BASE_URL",
        "LLM_FALLBACK_BASE_URL", "LLM_FALLBACK_API_KEY", "LLM_REASONING_EFFORT"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A clean environment with no .env file in the working directory."""
    monkeypatch.chdir(tmp_path)
    for name in VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_missing_model_is_a_clear_error(env):
    env.setenv("NVIDIA_API_KEY", "k")
    with pytest.raises(ConfigError, match="LLM_MODEL is not set.*build.nvidia.com"):
        load_settings()


def test_defaults_and_no_fallback(env):
    env.setenv("NVIDIA_API_KEY", "k")
    env.setenv("LLM_MODEL", "pub/model")
    s = load_settings()
    assert (s.model, s.base_url, s.fallbacks, s.reasoning_effort) == ("pub/model", DEFAULT_BASE_URL, (), "")


def test_fallback_list_uses_primary_endpoint_by_default(env):
    env.setenv("NVIDIA_API_KEY", "k")
    env.setenv("LLM_MODEL", "pub/model")
    env.setenv("LLM_MODEL_FALLBACK", " a/one, ,pub/model, a/two, a/one,")  # blanks, primary, repeats dropped
    s = load_settings()
    assert s.fallbacks == (Endpoint("a/one", DEFAULT_BASE_URL, "k"), Endpoint("a/two", DEFAULT_BASE_URL, "k"))
    assert [endpoint.model for endpoint in s.endpoints] == ["pub/model", "a/one", "a/two"]


def test_fallback_can_use_its_own_endpoint(env):
    env.setenv("NVIDIA_API_KEY", "k")
    env.setenv("LLM_MODEL", "pub/model")
    env.setenv("LLM_MODEL_FALLBACK", "other-model")
    env.setenv("LLM_FALLBACK_BASE_URL", "https://other.invalid/v1")
    env.setenv("LLM_FALLBACK_API_KEY", "other-key")
    assert load_settings().fallbacks == (Endpoint("other-model", "https://other.invalid/v1", "other-key"),)


def test_api_key_not_required_for_cache_only_runs(env):
    env.setenv("LLM_MODEL", "pub/model")
    with pytest.raises(ConfigError, match="NVIDIA_API_KEY"):
        load_settings()
    assert load_settings(require_api_key=False).api_key is None
