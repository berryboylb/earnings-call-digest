"""Merges items that state the same fact, and flags items that contradict each other."""

import re

from schema.verification import Amount, VerifiedItem
from utils.numbers import amounts_equal, parse_amounts


def merge_duplicates(items: list[VerifiedItem]) -> list[VerifiedItem]:
    """Merge items that make the same claim, and flag conflicting ones.

    Items make the same claim when they have the same kind, metric and period (and
    basis, for figures). Of those:
    - Same values: keep one (the verified copy if there is one). The others' evidence
      goes into its context, with a note "also stated by X". Nothing is thrown away.
    - Different values: never merged. If two or more are verified, they all become
      unverified, because code can't tell which one is right.
    """
    groups = {}
    for item in items:
        key = claim_key(item)
        if key is not None:
            groups.setdefault(key, []).append(item)

    merged_away = []
    for group in groups.values():
        if len(group) < 2:
            continue
        keepers = []
        for cluster in _cluster_by_value(group):
            keeper = _pick_keeper(cluster)
            for other in cluster:
                if other is not keeper:
                    _merge_into(keeper, other)
                    merged_away.append(other)
            keepers.append(keeper)
        _flag_conflicts(keepers)

    kept = [item for item in items if not any(item is gone for gone in merged_away)]
    for item in kept:
        item.update_status()
    return kept


def claim_key(item: VerifiedItem) -> tuple | None:
    """What an item is a claim about. Risks and Q&A topics aren't merged, so they have none."""
    fields = item.fields
    if item.kind == "figure":
        return ("figure", _normalise(fields["metric"]), _normalise(fields["period"]), fields["basis"])
    if item.kind == "guidance":
        return ("guidance", _normalise(fields["metric"]), _normalise(fields["period"]))
    return None


def _cluster_by_value(group: list[VerifiedItem]) -> list[list[VerifiedItem]]:
    clusters = []
    for item in group:
        for cluster in clusters:
            if _same_values(cluster[0], item):
                cluster.append(item)
                break
        else:
            clusters.append([item])
    return clusters


def _pick_keeper(cluster: list[VerifiedItem]) -> VerifiedItem:
    for item in cluster:
        if item.status == "verified":
            return item
    return cluster[0]


def _merge_into(keeper: VerifiedItem, other: VerifiedItem) -> None:
    if other.source is not None:
        keeper.context.append(other.source)
    keeper.context.extend(other.context)
    keeper.notes.append(f"also stated by {other.speaker or other.speaker_claimed}")


def _flag_conflicts(keepers: list[VerifiedItem]) -> None:
    verified = [item for item in keepers if item.status == "verified"]
    if len(verified) < 2:
        return
    values = " vs ".join(_value_text(item) for item in verified)
    for item in verified:
        item.reasons.append(
            f"conflicting values for the same metric and period ({values}): "
            "could be segment vs total, a correction, or a model error"
        )


def _same_values(a: VerifiedItem, b: VerifiedItem) -> bool:
    amounts_a = _amounts(a)
    amounts_b = _amounts(b)
    if not amounts_a or not amounts_b:
        return _normalise(_value_text(a)) == _normalise(_value_text(b))
    if len(amounts_a) != len(amounts_b):
        return False
    return all(amounts_equal(x, y) for x, y in zip(amounts_a, amounts_b))


def _amounts(item: VerifiedItem) -> list[Amount]:
    text = _value_text(item)
    return parse_amounts(text) or parse_amounts(text, include_plain_numbers=True)


def _value_text(item: VerifiedItem) -> str:
    return item.fields["value"] if item.kind == "figure" else item.fields["range"]


def _normalise(text: str) -> str:
    """Lowercase, with punctuation and extra spaces removed, for comparing names of metrics and periods."""
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())
