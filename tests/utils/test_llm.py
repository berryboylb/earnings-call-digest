import pytest

from utils.llm import strip_reasoning


@pytest.mark.parametrize("content, expected", [
    ("<think>a</think>{}", "{}"),
    ("<THINK>a\nb</THINK> {} ", "{}"),
    ("<think>a</think><think>b</think>{}", "{}"),
    ("reasoning without an opening tag</think>{}", "{}"),
    ("{} <think>unfinished", "{}"),
    ("<think>unfinished", ""),
])
def test_strip_reasoning(content, expected):
    assert strip_reasoning(content) == expected
