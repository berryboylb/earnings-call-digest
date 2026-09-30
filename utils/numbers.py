"""Reads money, percentages and basis points from text, and compares them."""

import re

from constants.numbers import (
    ABSOLUTE_TOLERANCE,
    AMOUNT,
    CENT_WORDS,
    CURRENCY_CODES,
    DIRECTION_BEFORE_NUMBER,
    DIRECTION_WINDOW,
    RANGE_JOINER,
    RELATIVE_TOLERANCE,
    SCALES,
    SHORT_SCALES,
    UNITS,
    UP_WORDS,
)
from schema.verification import Amount


def parse_amounts(text: str, include_plain_numbers: bool = False) -> list[Amount]:
    """Find every amount in the text: "$412.6 million", "41.3%", "120 basis points".

    Values are fully scaled, so "$94.9B", "$94.9 billion" and "$94,900 million" are equal.
    Years, counts and other plain numbers are left out, unless include_plain_numbers
    is True (then they come back with unit "number").
    """
    amounts = [_read_amount(match, text) for match in AMOUNT.finditer(text)]
    _complete_ranges(amounts, text)
    if include_plain_numbers:
        return amounts
    return [amount for amount in amounts if amount.unit != "number"]


def amounts_equal(a: Amount, b: Amount) -> bool:
    """True if two amounts are the same, allowing for how they're written.

    Units must match (basis points are compared as percentage points), and so must
    currencies and directions when both are known. Rounding is a mismatch: "$0.6" is
    not "$0.58".
    """
    if _unit_family(a) != _unit_family(b):
        return False
    if a.currency and b.currency and a.currency != b.currency:
        return False
    if a.direction and b.direction and a.direction != b.direction:
        return False
    value_a = _comparable_value(a)
    value_b = _comparable_value(b)
    tolerance = max(ABSOLUTE_TOLERANCE, RELATIVE_TOLERANCE * max(value_a, value_b))
    return abs(value_a - value_b) <= tolerance


def _read_amount(match: re.Match, text: str) -> Amount:
    currency = CURRENCY_CODES.get((match["currency"] or "").strip().lower())
    number = float(match["number"].replace(",", ""))
    scale_word = (match["scale"] or "").lower()
    unit_word = " ".join((match["unit"] or "").lower().split())
    end = match.end()

    # "5 m" without a currency marker isn't five million: read it as a plain number.
    if scale_word in SHORT_SCALES and currency is None:
        scale_word = ""
        unit_word = ""
        end = match.end("number")

    if unit_word in CENT_WORDS:
        unit = "currency"
        currency = currency or "USD"
        number = number / 100
    elif currency:
        unit = "currency"
    elif unit_word:
        unit = UNITS[unit_word]
    elif scale_word:
        unit = "currency"  # "94.9 billion" with no currency marker
    else:
        unit = "number"

    scale = SCALES.get(scale_word, 1.0)
    start = match.start()
    return Amount(
        raw=text[start:end].strip(),
        value=number * scale,
        unit=unit,
        currency=currency,
        direction=_direction_before(text, start),
        start=start,
        end=end,
        scale=scale,
    )


def _complete_ranges(amounts: list[Amount], text: str) -> None:
    """In a range, the first number takes the unit and scale of the second:
    "$1.60 to $1.64 billion" means $1.60 billion to $1.64 billion; "40 to 42%" means 40% to 42%."""
    for first, second in zip(amounts, amounts[1:]):
        between = text[first.end:second.start]
        if not RANGE_JOINER.fullmatch(between) or second.unit == "number":
            continue
        if first.unit == "number":
            first.unit = second.unit
            first.currency = second.currency
        if first.unit == second.unit and first.scale == 1.0 and second.scale != 1.0:
            first.value *= second.scale
            first.scale = second.scale


def _direction_before(text: str, start: int) -> str | None:
    """ "up" or "down" if the words just before the number say so ("up 12%"), otherwise None."""
    before = text[max(0, start - DIRECTION_WINDOW):start]
    match = DIRECTION_BEFORE_NUMBER.search(before)
    if match is None:
        return None
    return "up" if match["word"].lower() in UP_WORDS else "down"


def _unit_family(amount: Amount) -> str:
    if amount.unit in ("bps", "percentage_points"):
        return "points"
    return amount.unit


def _comparable_value(amount: Amount) -> float:
    if amount.unit == "bps":
        return amount.value / 100  # 100 basis points = 1 percentage point
    return amount.value
