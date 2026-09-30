"""Stage 2 of the Earnings Call Digest: LLM extraction of structured items with verbatim quotes.

It returns exactly what the model said plus an honest status per section. It does
not verify anything against the transcript; that is Stage 3.
"""

from .client import FixtureProvider, LlmError, NvidiaProvider, Provider
from .config import ConfigError, Settings, load_settings
from .extract import run_extraction
from .models import Extraction, ExtractionRun, Figure, Guidance, QaTopic, Risk, SectionResult, Usage

__all__ = [
    "ConfigError",
    "Extraction",
    "ExtractionRun",
    "Figure",
    "FixtureProvider",
    "Guidance",
    "LlmError",
    "NvidiaProvider",
    "Provider",
    "QaTopic",
    "Risk",
    "SectionResult",
    "Settings",
    "Usage",
    "load_settings",
    "run_extraction",
]
