# Format assumptions about transcript sources live here and only here.
"""Compiled regexes, word lists and constants used by the parser. No functions here."""

import re

MIN_WORDS = 1500
OPERATOR = "Operator"

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

# Safe-harbor language. A paragraph is boilerplate if it matches 2 or more of these.
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

# The end of a sentence: . ! ? or …, optionally followed by closing quotes or brackets.
SENTENCE_END = re.compile(r"[.!?…][\"'’”)\]]*$")
