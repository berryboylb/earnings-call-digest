from evaluation.scoring import evaluate
from tests.evaluation.conftest import (
    figure,
    gold_figure,
    gold_guidance,
    guidance,
    key,
    result,
)

REVENUE = "Revenue in the second quarter was $850 million, up 12% from the second quarter of 2025."


def outcome_of(evaluation, anchor_start):
    [entry] = [entry for entry in evaluation.entries if entry.anchor.startswith(anchor_start)]
    return entry


def test_verified_item_with_every_field_right_is_correct():
    evaluation = evaluate(key(figures=[gold_figure("Revenue in the second quarter was", "$850 million")]),
                          result(figure("F1", "$850 million", REVENUE)))
    assert outcome_of(evaluation, "Revenue").outcome == "correct"
    assert (evaluation.headline.correct_items, evaluation.headline.matched_items) == (1, 1)


def test_verified_item_with_wrong_value_is_verified_but_wrong():
    evaluation = evaluate(key(figures=[gold_figure("Revenue in the second quarter was", "$850 million")]),
                          result(figure("F1", "$85 million", REVENUE)))
    assert outcome_of(evaluation, "Revenue").outcome == "verified but wrong value"
    assert evaluation.headline.false_accepts == 1


def test_every_wrong_field_is_listed():
    evaluation = evaluate(
        key(figures=[gold_figure("GAAP operating margin was 18%", "18%", period=["Q2 2026"], basis="GAAP")]),
        result(figure("F1", "18%", "GAAP operating margin was 18%", period="FY 2026", basis="non-GAAP")))
    entry = outcome_of(evaluation, "GAAP operating margin")
    assert entry.outcome == "verified but wrong period, basis"
    assert entry.wrong_fields == ["period", "basis"]


def test_unverified_matching_item_is_held_back_by_the_gate_with_its_reasons():
    held_back = figure("F1", "$850 million", REVENUE, status="unverified", reasons=["conflicting values"])
    evaluation = evaluate(key(figures=[gold_figure("Revenue in the second quarter was", "$850 million")]),
                          result(held_back))
    entry = outcome_of(evaluation, "Revenue")
    assert (entry.outcome, entry.gate_reasons, entry.item_id) == ("found but held back by gate", ["conflicting values"], "F1")
    assert evaluation.headline.false_rejects == 1  # every field was right


def test_missed_but_flagged_by_the_recall_check():
    evaluation = evaluate(key(figures=[gold_figure("leaving free cash flow of $135 million", "$135 million")]),
                          result(missed=["$135 million"]))
    assert outcome_of(evaluation, "leaving").outcome == "missed, flagged by recall check"

    evaluation = evaluate(key(figures=[gold_figure("leaving free cash flow of $135 million", "$135 million")]),
                          result())
    assert outcome_of(evaluation, "leaving").outcome == "missed"


def test_one_quote_covering_two_entries_is_not_scored_twice():
    """The $850M item's quote also contains the 12% anchor. It pairs with the $850M entry only."""
    evaluation = evaluate(
        key(figures=[gold_figure("up 12% from the second quarter of 2025", "12%"),
                     gold_figure("Revenue in the second quarter was", "$850 million")]),
        result(figure("F1", "$850 million", REVENUE)))
    assert outcome_of(evaluation, "up 12%").outcome == "missed"
    assert outcome_of(evaluation, "Revenue").outcome == "correct"
    assert evaluation.headline.false_accepts == 0


def test_guidance_qualifier_captured_only_if_in_a_span():
    anchor = "We expect Q3 2026 revenue of $900 million to $950 million"
    qualifier = "That range reflects the existing business only"
    with_qualifier = guidance("G1", "$900 million to $950 million", anchor + ".",
                              context_texts=[qualifier + ". The proposed acquisition has not closed."])
    without = guidance("G1", "$900 million to $950 million", anchor + ".")

    entry = gold_guidance(anchor, "$900 million to $950 million", qualifier_anchor=qualifier)
    assert outcome_of(evaluate(key(guidance=[entry]), result(with_qualifier)), "We expect").qualifier_captured is True
    assert outcome_of(evaluate(key(guidance=[entry]), result(without)), "We expect").qualifier_captured is False


def test_must_not_counts_the_items_own_value_not_its_context():
    rule = {"kind": "figure", "value": "$480 million", "reason": "Backlog was corrected to $460 million"}
    stale = figure("F1", "$480 million", "Platform backlog at June 30 was $480 million.")
    corrected = figure("F2", "$460 million", "The correct platform backlog at June 30 is $460 million.",
                       context_texts=["Platform backlog at June 30 was $480 million."])

    violations = evaluate(key(must_not=[rule]), result(stale)).must_not_violations
    assert [(violation.item_id, violation.item_value) for violation in violations] == [("F1", "$480 million")]
    assert evaluate(key(must_not=[rule]), result(corrected)).must_not_violations == []


def test_unlabelled_extras_are_listed():
    evaluation = evaluate(key(figures=[gold_figure("Revenue in the second quarter was", "$850 million")]),
                          result(figure("F1", "$850 million", REVENUE),
                                 figure("F2", "$97,000", "Average contract value declined 3% to $97,000.")))
    assert [extra.item_id for extra in evaluation.unlabelled_extras] == ["F2"]
