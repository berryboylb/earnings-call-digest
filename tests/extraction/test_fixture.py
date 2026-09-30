import json
from pathlib import Path

import pytest

from extraction import Extraction, FixtureProvider, LlmError, run_extraction
from extraction.__main__ import main
from parsing import parse_file

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "northwind.extraction.json"
NORTHWIND = ROOT / "data" / "sample_northwind_q3fy26.txt"


def test_hand_written_fixture_round_trips():
    data = json.loads(FIXTURE.read_text())
    assert "hand-written" in data["_comment"].lower()
    run = run_extraction(parse_file(NORTHWIND), FixtureProvider(FIXTURE))
    assert run.model == "hand-written-fixture" and run.structured_output_mode == "fixture"
    assert run.usage.replayed_calls == 2 and run.usage.calls == 0
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


def test_cli_fixture_run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main([str(NORTHWIND), "--fixture", str(FIXTURE)]) == 0
    out = capsys.readouterr().out
    assert "[prepared] ok | replayed | figures 8, guidance 3, risks 3, qa_topics 0" in out
    assert "[qa] ok | replayed | figures 0, guidance 1, risks 1, qa_topics 3" in out
    assert (tmp_path / "out" / "sample_northwind_q3fy26.extraction.json").exists()
