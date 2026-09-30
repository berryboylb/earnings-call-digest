# Format assumptions about transcript sources live here and only here.
"""Compiled regexes, word lists and constants used by the parser. No functions here."""

import re

OPERATOR = "Operator"

# Warnings and errors: a transcript shorter than this may be incomplete; fewer speakers or
# segments than this is not a usable call.
MIN_WORDS = 1500
MIN_SPEAKERS = 2
MIN_SEGMENTS = 3
# How much of the last paragraph to show when warning that it ends mid-sentence.
TRUNCATION_PREVIEW_LENGTH = 40

# An invisible character some files start with.
BYTE_ORDER_MARK = "\ufeff"
# The curly apostrophe, treated like a straight one when comparing names ("O’Neil" = "O'Neil").
CURLY_APOSTROPHE = "’"

# Non-breaking and figure spaces that some sources put inside names and numbers.
NBSP_CHARS = ("\u00a0", "\u202f", "\u2007")

# A person's name on a speaker or roster line is 2 to 5 words ("Priya S. Raman").
NAME_MIN_WORDS = 2
NAME_MAX_WORDS = 5
# A title after a name is at most 12 words; anything longer is the rest of a sentence.
TITLE_MAX_WORDS = 12
# A title may end in a short abbreviation such as "Inc." or "Co."; longer words ending in
# "." mean a sentence ending.
ABBREVIATION_MAX_LEN = 4
# A name not in the participant list must appear as a label this many times to count.
MIN_LABEL_OCCURRENCES = 2
# The word an Operator uses when handing the line to an analyst ("next question comes from").
QA_HANDOFF_WORD = "question"

# How many "Name - Title" lines in a row, under a header we don't recognise, look like
# a participant list rather than a stray line.
MIN_UNRECOGNISED_ROSTER_ENTRIES = 2

# Participant-list headers (matched against the whole line, minus a trailing colon).
MANAGEMENT_HEADER = re.compile(r"(?:company|corporate)\s+participants|executives", re.I)
ANALYST_HEADER = re.compile(r"(?:conference\s+call|other)\s+participants|analysts", re.I)

# Separator between a name and its title: a spaced hyphen, double hyphen, en dash or
# em dash, or a comma. Examples: "Jane Doe - CFO", "Jane Doe – CFO", "Jane Doe, CFO".
NAME_TITLE_SEP = re.compile(r"\s+(?:--?|–|—)\s+|,\s+")

# "Operator" alone on a line, or "Operator:" followed by inline text.
OPERATOR_LINE = re.compile(r"operator\s*(?::\s*(?P<text>.*))?", re.I)

# Layout B: "Name: text". The name part (up to 60 chars, no colon) is validated separately.
INLINE_SPEAKER = re.compile(r"(?P<name>[^:]{1,60}?)\s*:\s+(?P<text>\S.*)")

# Generic labels some transcripts use for people they couldn't identify.
UNIDENTIFIED = re.compile(
    r"unidentified\s+(?:analyst|participant|speaker|company\s+representative)", re.I
)

# A word used when comparing names: letters, with inner ' or - ("o'neil", "jean-luc").
NAME_KEY_WORD = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")

# One word of a person's name: letters plus inner . ' ’ - ("S.", "O'Neil", "Jean-Luc").
NAME_TOKEN = re.compile(r"[^\W\d_](?:[^\W\d_]|['’.\-])*")
NAME_PARTICLES = {"de", "da", "di", "du", "del", "della", "van", "von", "der", "den", "la", "le", "bin", "al"}
# Capitalised words that show up in headings and greetings but never in a person's name.
NOT_NAME_WORDS = {
    "call", "conference", "earnings", "participants", "session", "remarks", "quarter",
    "results", "transcript", "presentation", "question", "questions", "answer",
    "answers", "operator", "instructions", "executives", "analysts", "thank", "thanks",
    "you", "good", "morning", "afternoon", "evening", "welcome", "everyone", "hello",
    "closing", "opening", "prepared", "company", "corporate", "fiscal", "financial",
    "highlights", "overview", "outlook", "guidance", "disclaimer", "statements",
}

# An explicit Q&A header on its own line: "Question-and-Answer Session",
# "Questions and Answers", "Q&A", "Q & A Session".
QA_HEADER = re.compile(
    r"(?:questions?[\s-]+(?:and|&)[\s-]+answers?|q\s*&\s*a)(?:\s+session)?\s*:?", re.I
)

# Operator wording that opens Q&A: "question-and-answer", "Q&A", "first question",
# "open the line(s)/floor/call for/to questions".
QA_START_PHRASES = re.compile(
    r"question[\s-]+and[\s-]+answer|\bq\s*&\s*a\b|first question"
    r"|open(?:\s+up)?\s+the\s+(?:lines?|floor|call)\s+(?:for|to)\s+questions",
    re.I,
)

# Safe-harbor language. A paragraph is boilerplate if it matches at least
# BOILERPLATE_MIN_MATCHES of these.
BOILERPLATE_MIN_MATCHES = 2
BOILERPLATE_PATTERNS = [
    re.compile(r"forward[\s-]+looking\s+statements?", re.I),
    re.compile(r"safe\s+harbou?r", re.I),
    re.compile(r"risks?\s+and\s+uncertaint", re.I),
    # "could differ materially", or "may cause actual results to differ materially"
    re.compile(r"\b(?:could|may|might)\b[^.]{0,60}?\bdiffer\s+materially", re.I),
    re.compile(r"private\s+securities\s+litigation\s+reform\s+act", re.I),
    # "non-GAAP ... reconciliation" in either order, within one paragraph
    re.compile(r"non-gaap.*reconcil|reconcil.*non-gaap", re.I),
]

# Sentences that commonly close a safe-harbor passage. They never count toward the
# 2-match threshold; inside a paragraph that is already flagged, they extend the
# boilerplate span to cover them.
BOILERPLATE_EXTENDERS = [
    # "Please see our filings with the SEC for more information."
    re.compile(
        r"see\s+our\s+(?:most\s+recent\s+)?(?:sec\s+filings|filings|(?:form\s+)?10-[kq]|annual\s+report)"
        r"\b.*?\bfor\s+(?:more|additional)\s+information",
        re.I,
    ),
    # "Please refer to our Form 10-K for a discussion of these risks."
    re.compile(
        r"refer\s+to\s+our\s+(?:most\s+recent\s+)?(?:filings|(?:form\s+)?10-[kq]|earnings\s+release)\b",
        re.I,
    ),
    # "Reconciliations are available in our earnings release."
    re.compile(r"reconciliations?\s+(?:are|is)\s+available", re.I),
]

# The end of a sentence: . ! ? or …, optionally followed by closing quotes or brackets.
SENTENCE_END = re.compile(r"[.!?…][\"'’”)\]]*$")

# A break between sentences: . ! ? (plus any closing quotes/brackets), whitespace, then an
# uppercase letter or opening quote. "$4.2 million", "3.5%" (no space after the dot) and
# "U.S. dollars" (lowercase after the space) are not breaks. The gap group is the whitespace.
SENTENCE_BREAK = re.compile(r"[.!?][\"'’”)\]]*(?P<gap>\s+)(?=[A-Z\"'“‘])")

# A line marking the end of the transcript, e.g. "END OF TRANSCRIPT", "[END]", "-- End --".
# Optional brackets, dashes or asterisks around "end" or "end of (the) transcript/call/document".
END_MARKER = re.compile(
    r"[\[(*\s\-–—]*end(?:\s+of\s+(?:the\s+)?(?:transcript|call|document))?[\])*\s\-–—]*",
    re.I,
)
