import json
import shutil
from pathlib import Path

from main import run
from providers.fixture import FixtureProvider

ROOT = Path(__file__).parents[1]
NORTHWIND = ROOT / "data" / "sample_northwind_q3fy26.txt"
FIXTURE = ROOT / "tests" / "fixtures" / "northwind.extraction.json"


def data_dir_with_northwind(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(NORTHWIND, data)
    return data


def test_run_parses_extracts_and_saves_every_transcript(tmp_path, capsys):
    ok = run(FixtureProvider(FIXTURE), data_dir_with_northwind(tmp_path), tmp_path / "out")
    out = capsys.readouterr().out

    assert ok is True
    assert "##### sample_northwind_q3fy26.txt" in out
    assert "15 segments (11 in Q&A), 7 speakers, roles from: participant_list" in out
    assert "warning: Transcript is short" in out
    assert "[prepared] ok | replayed | figures 8, guidance 3, risks 3, qa_topics 0" in out
    assert "[qa] ok | replayed | figures 0, guidance 1, risks 1, qa_topics 3" in out
    saved = json.loads((tmp_path / "out" / "sample_northwind_q3fy26.extraction.json").read_text())
    assert [section["status"] for section in saved["sections"]] == ["ok", "ok"]


def test_run_reports_failure(tmp_path, capsys):
    prepared_only = tmp_path / "prepared_only.json"
    prepared_only.write_text(json.dumps({"model": "m", "calls": {
        "prepared": {"figures": [], "guidance": [], "risks": [], "qa_topics": []}}}))

    ok = run(FixtureProvider(prepared_only), data_dir_with_northwind(tmp_path), tmp_path / "out")
    out = capsys.readouterr().out

    assert ok is False
    assert "[prepared] ok" in out and "[qa] failed | error: Fixture has no output for 'qa'." in out
