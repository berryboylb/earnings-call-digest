import pytest

from utils.text import split_sentences


def sentences(text):
    return [text[start:end] for start, end in split_sentences(text)]


@pytest.mark.parametrize("text", [
    "Revenue was $4.2 million this quarter.",
    "All figures are in U.S. dollars.",
    "Margin rose approximately 3.5% year over year.",
])
def test_splitter_keeps_numbers_and_abbreviations_intact(text):
    assert sentences(text) == [text]


def test_splitter_splits_on_sentence_breaks():
    text = 'Revenue was $4.2 million. Is that U.S. dollars? Yes! "Quoted," she said. \u201cCurly\u201d too.'
    assert sentences(text) == [
        "Revenue was $4.2 million.",
        "Is that U.S. dollars?",
        "Yes!",
        '"Quoted," she said.',
        "\u201cCurly\u201d too.",
    ]
