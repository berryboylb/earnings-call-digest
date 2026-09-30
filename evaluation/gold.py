"""Loads an answer key (data/<name>.gold.json) and checks its format."""

import json
from pathlib import Path

from pydantic import ValidationError

from schema.evaluation import AnswerKey


class AnswerKeyError(Exception):
    """The answer key file can't be used. The message names the entry at fault."""


def load_answer_key(path: Path) -> AnswerKey:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise AnswerKeyError(f"{path.name} is not valid JSON: {error}") from error

    try:
        return AnswerKey.model_validate(_without_comments(data))
    except ValidationError as error:
        problems = [f"{_where(problem['loc'])}: {_what(problem)}" for problem in error.errors()]
        raise AnswerKeyError(f"{path.name} has errors: " + "; ".join(problems)) from error


def _without_comments(data):
    """Drop every key starting with "_" (such as _comment and _todo), at any depth."""
    if isinstance(data, dict):
        return {key: _without_comments(value) for key, value in data.items() if not key.startswith("_")}
    if isinstance(data, list):
        return [_without_comments(value) for value in data]
    return data


def _where(location: tuple) -> str:
    """("figures", 3, "valu") becomes "figures[3].valu"."""
    text = ""
    for part in location:
        if isinstance(part, int):
            text += f"[{part}]"
        else:
            text += f".{part}" if text else str(part)
    return text


def _what(problem: dict) -> str:
    if problem["type"] == "extra_forbidden":
        return "unknown field"
    return problem["msg"]
