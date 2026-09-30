from parsing.parser import parse_transcript
from tests.verification.conftest import figure, guidance, make_run
from verification.verifier import verify_run

ANALYST_EXCHANGE = """\
Company Participants
Jane Doe - Chief Financial Officer
Conference Call Participants
Alex Chen - Citi

Operator
Welcome to the call. I will turn it over to Jane Doe.

Jane Doe
Thank you. Revenue was $100 million this quarter.

Operator
We will now begin the question-and-answer session. Our first question comes from Alex Chen with Citi.

Alex Chen
Is that $500 million target for next quarter?

Jane Doe
No, that is our full-year target.
"""


def test_number_only_in_an_analysts_question_needs_review():
    parsed = parse_transcript(ANALYST_EXCHANGE)
    item = guidance("Revenue target", "$500 million", "full year", "Jane Doe",
                    "No, that is our full-year target.",
                    context_quotes=["Is that $500 million target for next quarter?"])
    [verified] = verify_run(parsed, make_run(qa={"guidance": [item]})).items

    assert verified.status == "unverified"
    assert verified.reasons == ["number only appears in Alex Chen's (analyst) words; needs human confirmation"]


def test_failed_section_gives_no_items_and_passes_its_status_on(northwind):
    result = verify_run(northwind, make_run(qa="failed"))
    assert result.section_status == {"prepared": "ok", "qa": "failed"}
    assert [item for item in result.items if item.origin == "qa"] == []


def test_recall_lists_management_numbers_no_item_covers(planted):
    missed = [(candidate.segment_id, candidate.raw) for candidate in planted.possibly_missed]
    assert ("S4", "$61.4 million") in missed  # free cash flow: no item in the planted extraction
    assert all(raw != "$9 million" for _, raw in missed)  # inside the FX risk's quote, so covered
    assert all(raw != "30%" for _, raw in missed)  # said by an analyst, not management


def test_model_comparison_flag_is_a_note_and_the_transcript_decides(northwind):
    current = figure("Revenue", "$412.6 million", "Q3 fiscal 2026", "Priya Raman",
                     "Third quarter revenue was $412.6 million, compared to $371.2 million in the third quarter of last year.",
                     is_comparison=True)
    prior = figure("Prior-year revenue", "$371.2 million", "Q3 fiscal 2025", "Priya Raman",
                   "Third quarter revenue was $412.6 million, compared to $371.2 million in the third quarter of last year.",
                   is_comparison=True)
    items = verify_run(northwind, make_run(prepared={"figures": [current, prior]})).items

    assert items[0].status == "verified"  # the transcript presents $412.6M as the current result
    assert any("marked this figure as a prior-period comparison" in note for note in items[0].notes)
    assert items[1].reasons == ["$371.2 million is a prior-period comparison in the transcript, not a current result"]


def test_recall_skips_a_section_whose_extraction_failed(northwind):
    qa_empty = [candidate.raw for candidate in verify_run(northwind, make_run(qa={})).possibly_missed]
    assert "50 basis points" in qa_empty  # a Q&A number no item covers

    qa_failed = [candidate.raw for candidate in verify_run(northwind, make_run(qa="failed")).possibly_missed]
    assert "50 basis points" not in qa_failed  # Q&A wasn't extracted, so it isn't "missed"


def test_neutral_forward_word_is_not_hedging_language(northwind):
    forecast = {"theme": "Revenue expectation", "hedging_phrase": "expect", "speaker": "Priya Raman",
                "quote": "For the fourth quarter, we expect revenue between $425 million and $440 million."}
    real_risk = {"theme": "Tariffs", "hedging_phrase": "could pressure", "speaker": "Priya Raman",
                 "quote": "We also continue to monitor tariff developments, which could pressure component costs in the fourth quarter."}
    forecast_item, risk_item = verify_run(northwind, make_run(prepared={"risks": [forecast, real_risk]})).items
    assert forecast_item.reasons == ["not hedging language: 'expect'"]
    assert risk_item.status == "verified"
