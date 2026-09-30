import json
import shutil
from pathlib import Path

from main import run
from providers.fixture import FixtureProvider

ROOT = Path(__file__).parents[1]
NORTHWIND = ROOT / "tests" / "fixtures" / "sample_northwind_q3fy26.txt"
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
    saved = json.loads((tmp_path / "out" / "sample_northwind_q3fy26" / "extraction.json").read_text())
    assert [section["status"] for section in saved["sections"]] == ["ok", "ok"]

    assert out.index("=== 2. extract ===") < out.index("=== 3. verify ===")
    assert "19 items: 18 verified, 1 need review" in out
    verified = json.loads((tmp_path / "out" / "sample_northwind_q3fy26" / "verified.json").read_text())
    assert verified["section_status"] == {"prepared": "ok", "qa": "ok"}

    assert out.index("=== 3. verify ===") < out.index("=== 4. render ===")
    folder = tmp_path / "out" / "sample_northwind_q3fy26"
    assert (folder / "digest.html").exists() and (folder / "digest.docx").exists()
    assert "19 of 19 extracted items verified" not in out  # the fixture has one prior-period item
    assert "18 of 19 extracted items verified against the transcript" in out


def test_run_reports_failure(tmp_path, capsys):
    prepared_only = tmp_path / "prepared_only.json"
    prepared_only.write_text(json.dumps({"model": "m", "calls": {
        "prepared": {"figures": [], "guidance": [], "risks": [], "qa_topics": []}}}))

    ok = run(FixtureProvider(prepared_only), data_dir_with_northwind(tmp_path), tmp_path / "out")
    out = capsys.readouterr().out

    assert ok is False
    assert "[prepared] ok" in out and "[qa] failed | error: Fixture has no output for 'qa'." in out


def test_run_empties_the_output_folder_first(tmp_path):
    out = tmp_path / "out"
    (out / "old_transcript").mkdir(parents=True)
    (out / "old_transcript" / "digest.html").write_text("from a previous run")
    run(FixtureProvider(FIXTURE), data_dir_with_northwind(tmp_path), out)
    assert not (out / "old_transcript").exists()
    assert (out / "sample_northwind_q3fy26" / "digest.html").exists()
