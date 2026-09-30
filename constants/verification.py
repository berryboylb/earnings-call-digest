"""Thresholds and keyword rules used to verify extracted items against the transcript."""

import re

# --- Finding a quote in the transcript -----------------------------------------------

# A fuzzy match must score at least this (0 to 1) to count as the quote.
FUZZY_THRESHOLD = 0.9
# Quotes shorter than this many words must match exactly; too short to match fuzzily.
FUZZY_MIN_TOKENS = 4
# Fuzzy windows are the quote's length in words, plus or minus this many.
FUZZY_WINDOW_SLACK = 2
# A window is only scored if at least this share of the quote's words appear in it.
FUZZY_MIN_OVERLAP = 0.6

# --- Keyword rules ---------------------------------------------------------------------
# These are simple keyword rules, not language understanding. They catch the common
# wordings in earnings calls and will miss unusual ones.

# A currency figure preceded by one of these (in the same sentence, within
# PRIOR_PERIOD_WINDOW characters) is a prior-period number, not a current result.
PRIOR_PERIOD_WINDOW = 40
PRIOR_PERIOD_BEFORE = re.compile(
    r"\b(?:compared\s+(?:to|with)|versus|vs\.?|last\s+year|a\s+year\s+ago|prior[\s-]year|year[\s-]ago)\b"
    r"|\bfrom\s*$",  # "from" only right before the number: "grew to $5 million from $4 million"
    re.I,
)
# ...or followed by one of these.
PRIOR_PERIOD_AFTER = re.compile(r"^\s*in\s+the\s+(?:prior[\s-]year|year[\s-]ago)\s+quarter", re.I)

# Words that show each guidance direction. The sentence must contain one for the
# direction the model reported.
DIRECTION_CUES = {
    "raised": ["raise", "raising", "raised", "increase", "increasing", "up from our prior"],
    "lowered": ["lower", "lowering", "lowered", "reduce", "reducing", "reduced", "cut"],
    "reaffirmed": ["reaffirm", "reaffirming", "reaffirmed", "reiterate", "reiterating", "maintain", "maintaining"],
    "initiated": ["initiate", "initiating", "initiated", "introduce", "introducing", "introduced"],
}

# Outlook headings: the CFO usually announces which period the guidance that follows is for.
# "Let me start with some full year commentary for FY27." / "Now, to the outlook for our
# first quarter". A guidance item's period must agree with the nearest heading above it in
# the same speaker's turn. Only phrases that name a period count, so "Turning to our outlook."
# or "before I move to outlook" are not headings.
QUARTER_HEADING = re.compile(
    r"\b(?:outlook|commentary|guidance)\s+for\s+(?:our\s+|the\s+)?(?:first|second|third|fourth|next)\s+quarter\b"
    r"|\b(?:outlook|commentary|guidance)\s+for\s+Q[1-4]\b",
    re.I,
)
FULL_YEAR_HEADING = re.compile(
    r"\b(?:full[\s-]year|fiscal[\s-]year|annual)\s+(?:outlook|commentary|guidance)\b"
    r"|\b(?:outlook|commentary|guidance)\s+for\s+(?:the\s+)?(?:full[\s-]year|fiscal\s+year|FY\s?\d{2,4})\b",
    re.I,
)
# How a guidance item's period says which kind of period it is.
QUARTER_PERIOD = re.compile(r"\bQ[1-4]\b|\b(?:first|second|third|fourth|next)\s+quarter\b|\bquarter\b", re.I)
FULL_YEAR_PERIOD = re.compile(
    r"\bFY\s?'?\d{2,4}\b|\bfull[\s-]year\b|\bfiscal\s+(?:year\s+)?\d{2,4}\b|\bannual\b|^\s*(?:19|20)\d{2}\s*$",
    re.I,
)

# Forward-looking words that are not hedging on their own: "we expect revenue of X" is
# guidance, not a risk. A risk whose hedging phrase is only one of these is rejected.
NEUTRAL_FORWARD_WORDS = {
    "expect", "expected", "expects", "should", "will", "believe", "anticipate", "plan",
    "intend", "i think", "we think", "going forward",
}

# --- Output ----------------------------------------------------------------------------

# Characters of text shown either side of a possibly missed number.
MISSED_CONTEXT_CHARS = 60

# Item id prefixes, numbered in extraction order: F1, G1, R1, Q1.
ID_PREFIXES = {"figure": "F", "guidance": "G", "risk": "R", "qa": "Q"}
