"""Pairs answer-key entries with extracted items, using the verifier's tokenizer and number reader."""

from schema.verification import Amount, VerifiedItem
from utils.numbers import amounts_equal, parse_amounts
from verification.matching import tokenise


def normalise(text: str) -> str:
    """The verifier's tokens joined with single spaces: lowercase, straight quotes, no
    punctuation at word edges (except $ and %), no thousands separators."""
    return " ".join(token.text for token in tokenise(text))


def item_spans(item: VerifiedItem) -> list[str]:
    """The transcript text the item was found at, plus every context quote's text."""
    spans = [match.text for match in item.context]
    if item.source is not None:
        spans.insert(0, item.source.text)
    return spans


def matches(kind: str, anchor: str, item: VerifiedItem) -> bool:
    """True if the item is the same kind and the anchor appears in one of its spans."""
    if item.kind != kind:
        return False
    wanted = normalise(anchor)
    return any(wanted in normalise(span) for span in item_spans(item))


def period_ok(extracted_period: str, gold_period: str | list[str]) -> bool:
    """True if the extracted period is one of the accepted wordings, ignoring case,
    punctuation and spaces ("June 30 2026" = "June 30, 2026")."""
    accepted = gold_period if isinstance(gold_period, list) else [gold_period]
    extracted = normalise(extracted_period).replace(" ", "")
    return any(extracted == normalise(period).replace(" ", "") for period in accepted)


def numbers(text: str) -> list[Amount]:
    """The amounts in a value or range; a plain count ("38") if that's all there is."""
    return parse_amounts(text) or parse_amounts(text, include_plain_numbers=True)


def values_equal(text_a: str, text_b: str) -> bool:
    """True if two values (or ranges) contain the same numbers, in the same order."""
    amounts_a = numbers(text_a)
    amounts_b = numbers(text_b)
    if not amounts_a or len(amounts_a) != len(amounts_b):
        return False
    return all(amounts_equal(a, b) for a, b in zip(amounts_a, amounts_b))
