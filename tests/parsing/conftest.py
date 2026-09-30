"""Shared fixtures for the parsing tests."""

from pathlib import Path

import pytest

from parsing.parser import parse_file

KESTREL = Path(__file__).parents[1] / "fixtures" / "fictional_kestrel_q2.txt"
MERIDIAN = Path(__file__).parents[2] / "tests" / "fixtures" / "meridian.txt"

# Fictional Layout B transcript: inline "Name: text" and no participant list.
LAYOUT_B = """\
Acme Widgets Q1 2026 Earnings Call (fictional)

Operator: Good morning. I will now turn the call over to Tom Reyes, our CEO.
Tom Reyes: Thank you. Revenue was $10.0 million, up 5%.
Ana Lopez: Thanks, Tom. Gross margin was 30%. Tom Reyes: that label inside a sentence is not a speaker.
Operator: We will now open the line for questions. Our first question comes from Raj Patel with Barclays.
Raj Patel: How should we think about margins next year?
Ana Lopez: We expect them to be stable.
Mark Stone: I would add that pricing is holding up.
Operator: Our next question comes from Kim Wu with UBS.
Kim Wu: What about hiring?
Mark Stone: Hiring is flat.
"""


@pytest.fixture(scope="session")
def kestrel_path():
    return KESTREL


@pytest.fixture(scope="session")
def kestrel_text():
    return KESTREL.read_text()


@pytest.fixture(scope="session")
def parsed():
    return parse_file(KESTREL)


@pytest.fixture(scope="session")
def layout_b():
    return LAYOUT_B


@pytest.fixture(scope="session")
def by_speaker():
    def _by_speaker(result, name):
        return [segment for segment in result.segments if segment.speaker == name]
    return _by_speaker


@pytest.fixture(scope="session")
def meridian():
    return parse_file(MERIDIAN)
