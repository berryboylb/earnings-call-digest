from schema.verification import VerifiedItem
from tests.verification.conftest import make_run
from verification.checks import check_boilerplate, check_quote_found
from verification.matching import TranscriptIndex, find_quote, sentence_context
from verification.verifier import verify_run


def test_exact_match(northwind):
    index = TranscriptIndex(northwind)
    match = find_quote(index, "FREE CASH FLOW for the quarter was $61.4 million.")
    assert (match.segment_id, match.method, match.score) == ("S4", "exact", 1.0)
    assert match.text == "Free cash flow for the quarter was $61.4 million"


def test_fuzzy_match_passes_for_a_near_verbatim_quote(northwind):
    match = find_quote(TranscriptIndex(northwind),
                       "GAAP gross margins was 41.3%, up 120 basis points from a year ago, reflecting better mix.")
    assert match.method == "fuzzy" and match.score >= 0.9
    assert match.text.startswith("GAAP gross margin was 41.3%")


def test_fuzzy_match_rejects_a_paraphrase(northwind):
    index = TranscriptIndex(northwind)
    assert find_quote(index, "Gross margin improved sharply this year because of pricing and a better mix.") is None
    assert find_quote(index, "Revenue was strong.") is None  # under 4 words: exact only


def test_boilerplate_match_is_flagged(northwind):
    quote = "These statements are subject to risks and uncertainties, and actual results could differ materially"
    match = find_quote(TranscriptIndex(northwind), quote)
    assert match.segment_id == "S2" and match.in_boilerplate

    item = VerifiedItem(kind="risk", fields={"quote": quote}, speaker_claimed="Dana Whitfield", origin="prepared")
    assert check_quote_found(item, TranscriptIndex(northwind))
    check_boilerplate(item)
    assert item.reasons == ["quote is from the safe-harbor (legal boilerplate) text"]


def test_boilerplate_risk_is_unverified_end_to_end(northwind):
    risk = {"theme": "Legal", "hedging_phrase": "could differ materially", "speaker": "Dana Whitfield",
            "quote": "actual results could differ materially from those expressed or implied"}
    [item] = verify_run(northwind, make_run(prepared={"risks": [risk]})).items
    assert item.status == "unverified"
    assert "quote is from the safe-harbor (legal boilerplate) text" in item.reasons


def test_sentence_context_does_not_split_on_decimals_or_abbreviations():
    text = "Revenue was $4.2 million in the U.S. market. Costs rose."
    start = text.index("$4.2")
    sentence_start, sentence_end = sentence_context(text, start, start + 4)
    assert text[sentence_start:sentence_end] == "Revenue was $4.2 million in the U.S. market."
