"""Project folders, and the LLM settings read from .env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

DATA_DIR = Path("data")
OUTPUT_DIR = Path("out")

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_TEMPERATURE = 0.0
# One request may take minutes: long transcripts and reasoning models give long answers.
DEFAULT_TIMEOUT_SECONDS = 600.0
DEFAULT_CACHE_DIR = Path(".cache/llm")
# The most tokens one answer may use. Reasoning models count their hidden reasoning too:
# past answers used about 12,000 tokens per call, so this leaves room.
DEFAULT_MAX_TOKENS = 16384


class ConfigError(Exception):
    """A required setting is missing."""


@dataclass(frozen=True)
class Endpoint:
    """A model, and the API that serves it."""

    model: str
    base_url: str
    api_key: str | None


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str | None
    model: str
    fallbacks: tuple[Endpoint, ...] = ()  # tried in order if the main model's call fails
    reasoning_effort: str = ""  # empty means: don't send a reasoning setting
    temperature: float = DEFAULT_TEMPERATURE
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    max_tokens: int = DEFAULT_MAX_TOKENS
    cache_dir: Path = DEFAULT_CACHE_DIR

    @property
    def endpoints(self) -> tuple[Endpoint, ...]:
        """The main model first, then the fallbacks."""
        main = Endpoint(self.model, self.base_url, self.api_key)
        return (main, *self.fallbacks)


def load_settings(require_api_key: bool = True) -> Settings:
    """Read the settings from the environment and ./.env. Raises ConfigError if one is missing.

    Pass require_api_key=False for runs that only replay the cache and never call the API.
    """
    load_dotenv(find_dotenv(usecwd=True))

    model = _read_env("LLM_MODEL")
    if not model:
        raise ConfigError(
            "LLM_MODEL is not set. Copy the exact model ID from the model's page on "
            "build.nvidia.com and add it to .env, e.g. LLM_MODEL=<publisher>/<model-name>."
        )

    base_url = _read_env("LLM_BASE_URL") or DEFAULT_BASE_URL
    api_key = _read_env("NVIDIA_API_KEY") or None
    if require_api_key and not api_key:
        raise ConfigError("NVIDIA_API_KEY is not set. Add it to .env (see .env.example).")

    fallback_models = _fallback_models(main_model=model)
    fallback_base_url = _read_env("LLM_FALLBACK_BASE_URL") or base_url
    fallback_api_key = _read_env("LLM_FALLBACK_API_KEY") or api_key
    if require_api_key and fallback_models and not fallback_api_key:
        raise ConfigError("LLM_MODEL_FALLBACK is set but LLM_FALLBACK_API_KEY is not.")

    fallbacks = []
    for fallback_model in fallback_models:
        fallbacks.append(Endpoint(fallback_model, fallback_base_url, fallback_api_key))

    return Settings(
        base_url=base_url,
        api_key=api_key,
        model=model,
        fallbacks=tuple(fallbacks),
        reasoning_effort=_read_env("LLM_REASONING_EFFORT"),
        timeout=float(_read_env("LLM_TIMEOUT_SECONDS") or DEFAULT_TIMEOUT_SECONDS),
        max_tokens=int(_read_env("LLM_MAX_TOKENS") or DEFAULT_MAX_TOKENS),
    )


def _fallback_models(main_model: str) -> list[str]:
    """The models listed in LLM_MODEL_FALLBACK (comma-separated), in order.
    Blank entries, repeats and the main model itself are skipped."""
    models = []
    for model in _read_env("LLM_MODEL_FALLBACK").split(","):
        model = model.strip()
        if model and model != main_model and model not in models:
            models.append(model)
    return models


def _read_env(name: str) -> str:
    return os.environ.get(name, "").strip()
