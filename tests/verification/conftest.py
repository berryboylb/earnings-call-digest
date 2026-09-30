"""Shared fixtures for the verification tests."""

from pathlib import Path

import pytest

from extraction.extractor import run_extraction
from parsing.parser import parse_file
from providers.fixture import FixtureProvider
from schema.extraction import Extraction, ExtractionRun, SectionResult, Usage
from verification.verifier import verify_run

ROOT = Path(__file__).parents[2]
NORTHWIND = ROOT / "data" / "sample_northwind_q3fy26.txt"
MERIDIAN = ROOT / "data" / "meridian.txt"
PLANTED = ROOT / "tests" / "fixtures" / "northwind.planted.extraction.json"

EMPTY = {"figures": [], "guidance": [], "risks": [], "qa_topics": []}


def make_run(prepared: dict | None = None, qa: dict | str | None = None) -> ExtractionRun:
    """An extraction run built by hand. Pass qa="failed" for a failed Q&A section."""
    sections = [SectionResult(name="prepared", status="ok", extraction=Extraction(**{**EMPTY, **(prepared or {})}),
                              error=None, replayed=True)]
    if qa == "failed":
        sections.append(SectionResult(name="qa", status="failed", extraction=None, error="timed out", replayed=False))
    else:
        sections.append(SectionResult(name="qa", status="ok", extraction=Extraction(**{**EMPTY, **(qa or {})}),
                                      error=None, replayed=True))
    return ExtractionRun(sections=sections, model="test", fallback_models=[], prompt_version="v1",
                         structured_output_mode="fixture", usage=Usage())


def figure(metric, value, period, speaker, quote, context_quotes=(), basis="not stated", is_comparison=False):
    return {"metric": metric, "value": value, "period": period, "is_comparison": is_comparison, "basis": basis,
            "speaker": speaker, "quote": quote, "context_quotes": list(context_quotes)}


def guidance(metric, range_, period, speaker, quote, context_quotes=(), direction="not stated"):
    return {"metric": metric, "range": range_, "period": period, "direction": direction,
            "speaker": speaker, "quote": quote, "context_quotes": list(context_quotes)}


@pytest.fixture(scope="session")
def northwind():
    return parse_file(NORTHWIND)


@pytest.fixture(scope="session")
def meridian():
    return parse_file(MERIDIAN)


@pytest.fixture(scope="session")
def planted(northwind):
    """The planted-mistakes extraction, verified."""
    run = run_extraction(northwind, FixtureProvider(PLANTED))
    return verify_run(northwind, run)


@pytest.fixture(scope="session")
def find_item():
    def _find(result, **fields):
        matches = [item for item in result.items if all(item.fields.get(k) == v for k, v in fields.items())]
        assert len(matches) == 1, f"expected one item with {fields}, found {len(matches)}"
        return matches[0]
    return _find
