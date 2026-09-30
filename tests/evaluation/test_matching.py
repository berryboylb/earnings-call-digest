from evaluation.matching import matches, period_ok
from tests.evaluation.conftest import figure


def test_anchor_matches_through_a_context_span():
    item = figure("F1", "$460 million", "The correct platform backlog at June 30 is $460 million.",
                  context_texts=["Platform backlog at June 30 was $480 million."])
    assert matches("figure", "backlog at June 30 was $480 million", item)  # only in the context span
    assert matches("figure", "THE CORRECT platform backlog", item)  # case and punctuation ignored
    assert not matches("guidance", "The correct platform backlog", item)  # kinds must agree
    assert not matches("figure", "backlog at June 30 was $500 million", item)


def test_period_must_be_one_of_the_accepted_wordings():
    accepted = ["first six months of 2026", "H1 2026"]
    assert not period_ok("first six months 2026", accepted)  # not listed, so not accepted
    assert period_ok("First six months of 2026", accepted)
    assert period_ok("June 30 2026", "June 30, 2026")  # punctuation and spaces removed
    assert period_ok("Q2 2026", ["Q2 2026", "second quarter 2026"])
