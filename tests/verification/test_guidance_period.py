"""Guidance must carry the period the CFO announced before giving it. Made-up text in the style
of a real call: full-year commentary first, then "the outlook for our first quarter"."""

from parsing.parser import parse_transcript
from tests.verification.conftest import guidance, make_run
from verification.verifier import verify_run

CALL = """\
Acme Corp FY26 Fourth Quarter Earnings Conference Call
JANE DOE:
Thank you. Revenue was $12 billion, up 15%.
Now, moving to our outlook.
Let me start with some full year commentary for FY27.
We expect double-digit revenue growth, with full-year capital expenditure of over $50 billion.
Now, to the outlook for our first quarter, which unless noted otherwise is on a US dollar basis.
We expect revenue of $12.5 to $12.8 billion.
OPERATOR: Our first question comes from the line of Karl Smith with UBS. Please proceed.
KARL SMITH, UBS: Thanks. How durable is the growth?
JANE DOE: Very durable.
"""
Q1_QUOTE = "We expect revenue of $12.5 to $12.8 billion."
FY_QUOTE = "We expect double-digit revenue growth, with full-year capital expenditure of over $50 billion."


def verify(*items):
    return verify_run(parse_transcript(CALL), make_run(prepared={"guidance": list(items)})).items


def test_quarter_guidance_labelled_full_year_is_held_back():
    [item] = verify(guidance("Revenue", "$12.5 to $12.8 billion", "FY27", "Jane Doe", Q1_QUOTE))
    assert item.status == "unverified"
    assert item.reasons == ["period conflicts with the outlook heading: 'Now, to the outlook for our first quarter, "
                            "which unless noted otherwise is on a US dollar basis.'"]


def test_quarter_guidance_labelled_as_the_quarter_passes():
    [item] = verify(guidance("Revenue", "$12.5 to $12.8 billion", "Q1 FY27", "Jane Doe", Q1_QUOTE))
    assert item.status == "verified", item.reasons


def test_full_year_guidance_under_the_full_year_heading_passes():
    [item] = verify(guidance("Capital expenditure", "over $50 billion", "FY27", "Jane Doe", FY_QUOTE))
    assert item.status == "verified", item.reasons


def test_full_year_guidance_labelled_as_a_quarter_is_held_back():
    [item] = verify(guidance("Capital expenditure", "over $50 billion", "Q1 FY27", "Jane Doe", FY_QUOTE))
    assert item.reasons == ["period conflicts with the outlook heading: "
                            "'Let me start with some full year commentary for FY27.'"]


def test_a_mention_of_outlook_without_a_period_is_not_a_heading():
    call = CALL.replace("Let me start with some full year commentary for FY27.\n", "")
    [item] = verify_run(parse_transcript(call), make_run(prepared={"guidance": [
        guidance("Capital expenditure", "over $50 billion", "Q1 FY27", "Jane Doe", FY_QUOTE)]})).items
    assert item.status == "verified"  # "Now, moving to our outlook." names no period
