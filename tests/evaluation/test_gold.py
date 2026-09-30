import json
import shutil
from pathlib import Path

import pytest

from evaluation.gold import AnswerKeyError, load_answer_key
from main import run
from providers.fixture import FixtureProvider

ROOT = Path(__file__).parents[2]


def test_the_meridian_key_loads_and_ignores_comment_keys():
    answer_key = load_answer_key(ROOT / "data" / "meridian.gold.json")
    assert (len(answer_key.figures), len(answer_key.guidance), len(answer_key.risks), len(answer_key.must_not)) == (18, 4, 6, 3)


def test_unknown_field_is_a_clear_error_naming_the_entry(tmp_path):
    path = tmp_path / "bad.gold.json"
    path.write_text(json.dumps({"_comment": "fine", "figures": [
        {"anchor": "a", "value": "$1", "period": "Q1", "basis": "GAAP"},
        {"anchor": "b", "valu": "$2", "period": "Q1", "basis": "GAAP"},
    ]}))
    with pytest.raises(AnswerKeyError) as error:
        load_answer_key(path)
    message = str(error.value)
    assert "figures[1].valu: unknown field" in message
    assert "figures[1].value: Field required" in message


def test_no_answer_key_skips_evaluation(tmp_path, capsys):
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(ROOT / "data" / "sample_northwind_q3fy26.txt", data)
    run(FixtureProvider(ROOT / "tests" / "fixtures" / "northwind.extraction.json"), data, tmp_path / "out")
    assert "no answer key for sample_northwind_q3fy26, skipping evaluation" in capsys.readouterr().out
    assert not (tmp_path / "out" / "sample_northwind_q3fy26" / "eval.json").exists()
