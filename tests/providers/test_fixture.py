import json
from pathlib import Path

import pytest

from extraction.extractor import run_extraction
from parsing.parser import parse_file
from providers.base import LlmError
from providers.fixture import FixtureProvider
from schema.extraction import Extraction

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "northwind.extraction.json"
NORTHWIND = ROOT / "tests" / "fixtures" / "sample_northwind_q3fy26.txt"


def test_hand_written_fixture_round_trips():
    data = json.loads(FIXTURE.read_text())
    assert "hand-written" in data["_comment"].lower()
    run = run_extraction(parse_file(NORTHWIND), FixtureProvider(FIXTURE))
    assert run.model == "hand-written-fixture" and run.structured_output_mode == "fixture"
    # three prepared-remarks speaker turns and the Q&A, each answered from the fixture
    assert run.usage.replayed_calls == 4 and run.usage.calls == 0
    for section in run.sections:
        assert section.status == "ok" and section.replayed is True
        assert section.extraction.model_dump(mode="json") == data["calls"][section.name]


def test_fixture_quotes_are_verbatim():
    # Guards the fixture itself; this is not the pipeline's verification step.
    text = " ".join(NORTHWIND.read_text().split())
    data = json.loads(FIXTURE.read_text())
    for section in data["calls"].values():
        for items in section.values():
            for item in items:
                for quote in [item["quote"], *item.get("context_quotes", [])]:
                    assert quote in text, quote


def test_invalid_fixture_output_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"model": "m", "calls": {"prepared": {"figures": "nope"}}}))
    with pytest.raises(LlmError, match="failed validation"):
        FixtureProvider(bad).complete("prepared", "", "", Extraction)
