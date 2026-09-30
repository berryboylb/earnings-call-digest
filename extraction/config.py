"""Settings for the LLM provider, read from the environment (and .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROMPT_VERSION = "v1"

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_CACHE_DIR = Path(".cache/llm")


class ConfigError(Exception):
    """A required setting is missing."""


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str | None
    model: str
    reasoning_effort: str = ""  # empty: send no reasoning parameter
    temperature: float = DEFAULT_TEMPERATURE
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    cache_dir: Path = DEFAULT_CACHE_DIR


def load_settings(require_api_key: bool = True) -> Settings:
    """Build Settings from the environment. Raises ConfigError if something required is unset.

    `require_api_key=False` is for cache-only runs, which never call the API.
    """
    load_dotenv()
    model = os.environ.get("LLM_MODEL", "").strip()
    if not model:
        raise ConfigError(
            "LLM_MODEL is not set. Copy the exact model ID from the model's page on "
            "build.nvidia.com and add it to .env, e.g. LLM_MODEL=<publisher>/<model-name>."
        )
    api_key = os.environ.get("NVIDIA_API_KEY", "").strip() or None
    if require_api_key and not api_key:
        raise ConfigError("NVIDIA_API_KEY is not set. Add it to .env (see .env.example).")
    return Settings(
        base_url=os.environ.get("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL,
        api_key=api_key,
        model=model,
        reasoning_effort=os.environ.get("LLM_REASONING_EFFORT", "").strip(),
    )
