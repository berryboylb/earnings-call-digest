from parsing.parser import parse_transcript
from tests.verification.conftest import guidance, make_run
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
