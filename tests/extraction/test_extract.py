import json
from pathlib import Path

from extraction import Extraction, LlmError, Usage, run_extraction
from extraction.__main__ import main
from parsing import Paragraph, ParsedTranscript, Segment, parse_file

DATA = Path(__file__).parents[2] / "data"


class FakeProvider:
    """Records calls; raises LlmError for the section names in `fail`."""

    def __init__(self, fail=()):
        self.model, self.usage, self.structured_output_mode = "fake/model", Usage(), "json_schema"
        self.fail, self.calls = set(fail), []

    def complete(self, name, system, user, schema):
        self.calls.append(name)
        if name in self.fail:
            raise LlmError("upstream timed out")
        return Extraction(figures=[], guidance=[], risks=[], qa_topics=[]), False


def test_failure_in_qa_marks_only_qa_failed():
    provider = FakeProvider(fail={"qa"})
    run = run_extraction(parse_file(DATA / "meridian.txt"), provider)
    prepared, qa = run.sections
    assert (prepared.name, prepared.status, prepared.error) == ("prepared", "ok", None)
    assert prepared.extraction is not None
    assert (qa.name, qa.status, qa.error) == ("qa", "failed", "upstream timed out")
    assert qa.extraction is None  # never an empty Extraction standing in for a failure
    assert provider.calls == ["prepared", "qa"]


def test_empty_qa_input_is_not_sent():
    segs = [Segment(f"S{i}", name, "management", "prepared", [Paragraph("Revenue was $5 million.")])
            for i, name in enumerate(["Jane Doe", "John Roe", "Jane Doe"], start=1)]
    parsed = ParsedTranscript(participants=[], segments=segs, roster_source="heuristic")
    provider = FakeProvider()
    run = run_extraction(parsed, provider)
    assert [(s.name, s.status) for s in run.sections] == [("prepared", "ok"), ("qa", "empty_input")]
    assert run.sections[1].extraction is None and run.sections[1].error is None
    assert provider.calls == ["prepared"]


def test_cli_exits_2_when_a_section_fails(tmp_path, monkeypatch, capsys):
    fixture = tmp_path / "prepared_only.json"
    fixture.write_text(json.dumps({"model": "m", "calls": {
        "prepared": {"figures": [], "guidance": [], "risks": [], "qa_topics": []}}}))
    monkeypatch.chdir(tmp_path)
    code = main([str(DATA / "sample_northwind_q3fy26.txt"), "--fixture", str(fixture)])
    out = capsys.readouterr().out
    assert code == 2
    assert "[prepared] ok" in out and "[qa] failed | error: Fixture has no output for 'qa'." in out
    saved = json.loads((tmp_path / "out" / "sample_northwind_q3fy26.extraction.json").read_text())
    assert [s["status"] for s in saved["sections"]] == ["ok", "failed"]
