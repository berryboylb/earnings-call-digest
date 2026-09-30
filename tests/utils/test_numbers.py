import pytest

from utils.numbers import amounts_equal, parse_amounts


def one(text):
    [amount] = parse_amounts(text)
    return amount


@pytest.mark.parametrize("other", ["94.9 billion", "$94,900 million", "US$94.9 billion"])
def test_same_amount_written_differently_is_equal(other):
    assert amounts_equal(one("$94.9B"), one(other))


def test_rounding_is_a_mismatch():
    assert not amounts_equal(one("$0.6"), one("$0.58"))
    assert not amounts_equal(one("$1.2 billion"), one("$1.25 billion"))


def test_direction_is_kept_separate_from_value():
    down = one("Average contract value declined 3% year over year.")
    assert (down.value, down.direction) == (3.0, "down")
    assert one("a decline of 200 basis points").direction == "down"
    assert one("up 120 basis points").direction == "up"
    assert not amounts_equal(one("up 3%"), one("down 3%"))
    assert amounts_equal(one("3%"), one("down 3%"))  # direction only compared when both have one


@pytest.mark.parametrize("text", ["$1.60 to $1.64 billion", "$1.60–$1.64 billion", "$1.60 billion to $1.64 billion"])
def test_range_scale_carries_back_to_first_number(text):
    low, high = parse_amounts(text)
    assert (low.value, high.value) == (1.60e9, 1.64e9)


def test_range_unit_carries_back_to_first_number():
    low, high = parse_amounts("gross margin of 40 to 42%")
    assert (low.unit, low.value, high.value) == ("percent", 40.0, 42.0)


def test_years_counts_and_plain_numbers_are_not_amounts():
    assert parse_amounts("In Q3 fiscal 2026 we added 38 customers, bringing our total to 1,140. See our 10-K.") == []
    assert [a.value for a in parse_amounts("38", include_plain_numbers=True)] == [38.0]


def test_units_must_match():
    assert amounts_equal(one("1.2 percentage points"), one("120 bps"))
    assert not amounts_equal(one("12%"), one("$12"))
    assert not amounts_equal(one("EUR 92 million"), one("$92 million"))
