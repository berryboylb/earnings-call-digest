"""How money, percentages and basis points are written in transcripts."""

import re

# Currency markers, and the currency code each one stands for.
CURRENCY_CODES = {
    "us$": "USD", "$": "USD", "usd": "USD",
    "€": "EUR", "eur": "EUR",
    "£": "GBP", "gbp": "GBP",
    "¥": "JPY", "jpy": "JPY",
    "₦": "NGN", "ngn": "NGN",
}

# Words that multiply a number: "$1.6 billion", "$94.9B", "$97k".
SCALES = {
    "trillion": 1e12, "billion": 1e9, "million": 1e6, "thousand": 1e3,
    "bn": 1e9, "mn": 1e6, "b": 1e9, "m": 1e6, "k": 1e3,
}
# Short scales ("m", "b", "k", "bn", "mn") only count after a currency marker ("$5m"),
# so "5 m" in ordinary text isn't read as five million.
SHORT_SCALES = {"bn", "mn", "b", "m", "k"}

# Unit words after a number, and the unit each one means.
UNITS = {
    "%": "percent", "percent": "percent", "per cent": "percent",
    "percentage point": "percentage_points", "percentage points": "percentage_points",
    "basis point": "bps", "basis points": "bps", "bps": "bps", "bp": "bps",
}
# "27 cents" is $0.27.
CENT_WORDS = {"cent", "cents"}

# One amount: an optional currency marker, a number, an optional scale, an optional unit.
# The number must not be part of a word ("Q3") or another number.
AMOUNT = re.compile(
    r"""
    (?<![\w.$€£¥₦])
    (?P<currency>US\$|\$|€|£|¥|₦|(?:USD|EUR|GBP|JPY|NGN)\s?)?
    (?P<number>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    (?:\s?(?P<scale>trillion|billion|million|thousand|bn|mn|m|b|k)(?!\w))?
    (?:\s?(?P<unit>%|percentage\s+points?|per\s?cent|basis\s+points?|bps|bp|cents?)(?!\w))?
    """,
    re.X | re.I,
)

# Words between two numbers that make them a range: "$1.60 to $1.64 billion", "40–42%",
# "between $89.85 and $90.95 billion".
RANGE_JOINER = re.compile(r"\s*(?:to|and|–|—|-)\s*", re.I)

# Words just before a number that say which way it moved: "up 12%", "declined 3%",
# "a decline of 200 basis points". The number's value never becomes negative.
UP_WORDS = ["up", "grew", "grow", "grown", "increased", "increase", "rose", "risen", "higher", "gained"]
DOWN_WORDS = ["down", "declined", "decline", "decreased", "decrease", "fell", "fallen", "lower", "dropped"]
DIRECTION_WINDOW = 30  # how many characters before the number to look for those words
DIRECTION_BEFORE_NUMBER = re.compile(
    r"\b(?P<word>" + "|".join(UP_WORDS + DOWN_WORDS) + r")\s+"
    r"(?:by\s+|of\s+)?(?:about\s+|approximately\s+|roughly\s+|nearly\s+|almost\s+)?$",
    re.I,
)

# Two amounts are equal if they differ by at most the larger of these.
ABSOLUTE_TOLERANCE = 0.005
RELATIVE_TOLERANCE = 0.001  # 0.1% of the value
