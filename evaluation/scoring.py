"""Scores a verification result against a hand-written answer key.

Every answer-key entry gets one outcome: correct, verified but wrong, held back by the
gate, missed but flagged by the recall check, or missed.
"""

from constants.evaluation import (
    CORRECT,
    HELD_BACK,
    MISSED,
    MISSED_BUT_FLAGGED,
    VERIFIED_BUT_WRONG,
)
from evaluation.matching import (
    item_spans,
    matches,
    normalise,
    numbers,
    period_ok,
    values_equal,
)
from schema.evaluation import (
    AnswerKey,
    EntryResult,
    Evaluation,
    Headline,
    MustNotViolation,
    UnlabelledExtra,
)
from schema.verification import VerificationResult, VerifiedItem
from utils.numbers import amounts_equal


def evaluate(key: AnswerKey, result: VerificationResult) -> Evaluation:
    figure_items = _pair(key.figures, "figure", "value", result.items)
    guidance_items = _pair(key.guidance, "guidance", "range", result.items)

    entries = []
    for entry, item in zip(key.figures, figure_items):
        entries.append(_score_figure(entry, item, result))
    for entry, item in zip(key.guidance, guidance_items):
        entries.append(_score_guidance(entry, item, result))
    for entry in key.risks:
        entries.append(_score_risk(entry, result))

    violations = _must_not_violations(key, result)
    extras = _unlabelled_extras(key, result)
    headline = _headline(entries, figure_items + guidance_items, violations)
    return Evaluation(headline=headline, entries=entries, must_not_violations=violations, unlabelled_extras=extras)


# --- Pairing entries with items -----------------------------------------------------------

def _pair(entries: list, kind: str, value_field: str, items: list[VerifiedItem]) -> list[VerifiedItem | None]:
    """Pick at most one item per entry, and use each item for at most one entry.

    First pass: items whose quote contains the entry's anchor AND whose value matches it.
    Second pass: for entries still without an item, any unused item whose quote contains the
    anchor. So one quote that covers two entries isn't scored against both.
    """
    chosen = [None] * len(entries)
    used = []

    def unused_matches(entry, value_must_match):
        found = []
        for item in items:
            if any(item is taken for taken in used) or not matches(kind, entry.anchor, item):
                continue
            if value_must_match and not values_equal(item.fields[value_field], getattr(entry, value_field)):
                continue
            found.append(item)
        return found

    for value_must_match in (True, False):
        for i, entry in enumerate(entries):
            if chosen[i] is not None:
                continue
            item = _prefer_verified(unused_matches(entry, value_must_match))
            if item is not None:
                chosen[i] = item
                used.append(item)
    return chosen


def _prefer_verified(items: list[VerifiedItem]) -> VerifiedItem | None:
    for item in items:
        if item.status == "verified":
            return item
    return items[0] if items else None


# --- Scoring each kind ------------------------------------------------------------------------

def _score_figure(entry, item: VerifiedItem | None, result: VerificationResult) -> EntryResult:
    expected = f"{entry.value} · {_first(entry.period)} · {entry.basis}"
    if item is None:
        return EntryResult(kind="figure", anchor=entry.anchor, expected=expected,
                           outcome=_missed_outcome(entry.value, result))
    wrong = []
    if not values_equal(item.fields["value"], entry.value):
        wrong.append("value")
    if not period_ok(item.fields["period"], entry.period):
        wrong.append("period")
    if item.fields["basis"] != entry.basis:
        wrong.append("basis")
    return _found("figure", entry.anchor, expected, item, wrong)


def _score_guidance(entry, item: VerifiedItem | None, result: VerificationResult) -> EntryResult:
    expected = f"{entry.range} · {_first(entry.period)} · {entry.direction}"
    qualifier_captured = None
    if entry.qualifier_anchor is not None:
        qualifier_captured = item is not None and any(
            normalise(entry.qualifier_anchor) in normalise(span) for span in item_spans(item)
        )

    if item is None:
        result_entry = EntryResult(kind="guidance", anchor=entry.anchor, expected=expected,
                                   outcome=_missed_outcome(entry.range, result))
    else:
        wrong = []
        if not values_equal(item.fields["range"], entry.range):
            wrong.append("range")
        if not period_ok(item.fields["period"], entry.period):
            wrong.append("period")
        if item.fields["direction"] != entry.direction:
            wrong.append("direction")
        result_entry = _found("guidance", entry.anchor, expected, item, wrong)

    result_entry.qualifier_captured = qualifier_captured
    return result_entry


def _score_risk(entry, result: VerificationResult) -> EntryResult:
    candidates = [item for item in result.items if matches("risk", entry.anchor, item)]
    item = _prefer_verified(candidates)
    if item is None:
        return EntryResult(kind="risk", anchor=entry.anchor, expected=entry.theme, outcome=MISSED)
    return _found("risk", entry.anchor, entry.theme, item, wrong=[])


def _found(kind: str, anchor: str, expected: str, item: VerifiedItem, wrong: list[str]) -> EntryResult:
    """The outcome when an item was paired with the entry."""
    if item.status == "verified":
        outcome = CORRECT if not wrong else VERIFIED_BUT_WRONG.format(fields=", ".join(wrong))
        return EntryResult(kind=kind, anchor=anchor, expected=expected, outcome=outcome,
                           item_id=item.id, wrong_fields=wrong)
    return EntryResult(kind=kind, anchor=anchor, expected=expected, outcome=HELD_BACK,
                       item_id=item.id, wrong_fields=wrong, gate_reasons=item.reasons)


def _missed_outcome(value: str, result: VerificationResult) -> str:
    """No item for this entry. Did the recall check at least flag one of its numbers?"""
    for wanted in numbers(value):
        for candidate in result.possibly_missed:
            if any(amounts_equal(wanted, flagged) for flagged in numbers(candidate.raw)):
                return MISSED_BUT_FLAGGED
    return MISSED


# --- must_not, extras, headline ---------------------------------------------------------------

def _must_not_violations(key: AnswerKey, result: VerificationResult) -> list[MustNotViolation]:
    """A verified item whose own value (not its context) equals a forbidden value."""
    violations = []
    for rule in key.must_not:
        forbidden = numbers(rule.value)
        for item in result.items:
            if item.kind != rule.kind or item.status != "verified":
                continue
            item_value = item.fields["value"] if item.kind == "figure" else item.fields["range"]
            if any(amounts_equal(a, b) for a in numbers(item_value) for b in forbidden):
                violations.append(MustNotViolation(kind=rule.kind, value=rule.value, reason=rule.reason,
                                                   item_id=item.id, item_value=item_value))
    return violations


def _unlabelled_extras(key: AnswerKey, result: VerificationResult) -> list[UnlabelledExtra]:
    """Verified figures and guidance that no answer-key entry mentions. For manual review."""
    extras = []
    for item in result.items:
        if item.status != "verified" or item.kind not in ("figure", "guidance"):
            continue
        entries = key.figures if item.kind == "figure" else key.guidance
        if any(matches(item.kind, entry.anchor, item) for entry in entries):
            continue
        value = item.fields["value"] if item.kind == "figure" else item.fields["range"]
        extras.append(UnlabelledExtra(item_id=item.id, kind=item.kind,
                                      description=f"{item.fields['metric']}: {value} ({item.fields['period']})"))
    return extras


def _headline(entries: list[EntryResult], paired_items: list, violations: list) -> Headline:
    verified_paired = [item for item in paired_items if item is not None and item.status == "verified"]
    correct_ids = {entry.item_id for entry in entries if entry.outcome == CORRECT and entry.kind != "risk"}

    coverage = {}
    for kind in ("figure", "guidance", "risk"):
        of_kind = [entry for entry in entries if entry.kind == kind]
        coverage[kind] = [sum(1 for entry in of_kind if entry.outcome == CORRECT), len(of_kind)]

    with_qualifier = [entry for entry in entries if entry.qualifier_captured is not None]
    return Headline(
        correct_items=sum(1 for item in verified_paired if item.id in correct_ids),
        matched_items=len(verified_paired),
        coverage=coverage,
        qualifiers_captured=sum(1 for entry in with_qualifier if entry.qualifier_captured),
        qualifiers_total=len(with_qualifier),
        violations=len(violations),
        false_accepts=sum(1 for entry in entries if entry.outcome.startswith("verified but wrong")),
        false_rejects=sum(1 for entry in entries if entry.outcome == HELD_BACK and not entry.wrong_fields),
    )


def _first(period: str | list[str]) -> str:
    return period if isinstance(period, str) else period[0]
