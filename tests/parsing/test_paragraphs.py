import pytest

from constants.parsing import BOILERPLATE_EXTENDERS
from parsing.paragraphs import segment_text, split_paragraphs


def test_safe_harbor_flagged_as_boilerplate(parsed, by_speaker):
    ir = by_speaker(parsed, "Sofia Marquez")[0]
    # The closing "Please see our filings..." sentence is covered by an extender.
    assert [paragraph.boilerplate for paragraph in ir.paragraphs] == [False, True, False]
    assert "forward-looking" in ir.paragraphs[1].text
    assert "forward-looking" not in segment_text(ir)
    assert "forward-looking" in segment_text(ir, include_boilerplate=True)
    assert "Please see our filings" not in segment_text(ir)
    others = [paragraph for segment in parsed.segments if segment is not ir for paragraph in segment.paragraphs]
    assert not any(paragraph.boilerplate or paragraph.boilerplate_spans for paragraph in others)


def test_partly_boilerplate_paragraph_keeps_surrounding_sentences(meridian):
    s2 = meridian.segments[1]
    assert s2.speaker == "Emma Chen"
    assert len(s2.paragraphs) == 1
    para = s2.paragraphs[0]
    assert para.boilerplate_spans and not para.boilerplate
    assert para.text.startswith("Thank you. Joining me are")  # full text kept for verification

    currency = "All dollar figures are US dollars unless we explicitly say otherwise."
    assert currency in para.text[para.boilerplate_spans[0][1]:]  # after the span

    text = segment_text(s2)
    assert currency in text
    assert "Joining me are Daniel Okafor, our CEO, and Priya Shah, our CFO." in text
    assert "All dollar figures are US dollars" in text
    for safe_harbor in ["forward-looking", "may differ materially", "reconciliations"]:
        assert safe_harbor not in text
        assert safe_harbor in segment_text(s2, include_boilerplate=True)


@pytest.mark.parametrize("sentence", [
    "Please see our filings with the SEC for more information.",
    "Please see our most recent Form 10-K for additional information.",
    "Please refer to our earnings release for details.",
    "Reconciliations are available on our website.",
])
def test_extender_patterns_match_closing_sentences(sentence):
    assert any(pattern.search(sentence) for pattern in BOILERPLATE_EXTENDERS)


@pytest.mark.parametrize("text", [
    # extender sentences only
    "Please see our filings with the SEC for more information. Reconciliations are available online.",
    # one real pattern plus an extender: still below the 2-match threshold
    "Our plans involve risks and uncertainties. Please see our filings for more information.",
])
def test_extenders_alone_do_not_flag_a_paragraph(text):
    [para] = split_paragraphs([text])
    assert para.boilerplate_spans == []
