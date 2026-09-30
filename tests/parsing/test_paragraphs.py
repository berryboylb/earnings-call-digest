import pytest

from parsing import segment_text
from parsing.paragraphs import split_sentences


def sentences(text):
    return [text[s:e] for s, e in split_sentences(text)]


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


def test_safe_harbor_flagged_as_boilerplate(parsed, by_speaker):
    ir = by_speaker(parsed, "Sofia Marquez")[0]
    # The safe-harbor paragraph ends with "Please see our filings...", which matches no
    # pattern and follows the last matching sentence, so it is only partly boilerplate.
    assert [p.boilerplate for p in ir.paragraphs] == [False, False, False]
    assert [bool(p.boilerplate_spans) for p in ir.paragraphs] == [False, True, False]
    assert "forward-looking" in ir.paragraphs[1].text
    assert "forward-looking" not in segment_text(ir)
    assert "forward-looking" in segment_text(ir, include_boilerplate=True)
    assert "Please see our filings with the SEC for more information." in segment_text(ir)
    others = [p for s in parsed.segments if s is not ir for p in s.paragraphs]
    assert not any(p.boilerplate or p.boilerplate_spans for p in others)


def test_partly_boilerplate_paragraph_keeps_surrounding_sentences(meridian):
    s2 = meridian.segments[1]
    assert s2.speaker == "Emma Chen"
    assert len(s2.paragraphs) == 1
    para = s2.paragraphs[0]
    assert para.boilerplate_spans and not para.boilerplate
    assert para.text.startswith("Thank you. Joining me are")  # full text kept for verification

    text = segment_text(s2)
    assert "Joining me are Daniel Okafor, our CEO, and Priya Shah, our CFO." in text
    assert "All dollar figures are US dollars" in text
    for safe_harbor in ["forward-looking", "may differ materially", "reconciliations"]:
        assert safe_harbor not in text
        assert safe_harbor in segment_text(s2, include_boilerplate=True)
