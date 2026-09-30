"""Outcome labels and fixed text for the evaluation against a hand-written answer key."""

# The outcome for each answer-key entry. "verified but wrong" is followed by the wrong fields.
CORRECT = "correct"
VERIFIED_BUT_WRONG = "verified but wrong {fields}"
HELD_BACK = "found but held back by gate"
MISSED_BUT_FLAGGED = "missed, flagged by recall check"
MISSED = "missed"

ANSWER_KEY_SUFFIX = ".gold.json"  # data/meridian.gold.json is the key for data/meridian.txt
ANCHOR_PREVIEW_LENGTH = 50

NOTES = (
    "Verified means grounded in the transcript. This evaluation measures whether the "
    "grounded items are also correct and complete."
)
MATCHING_NOTE = (
    "Each extracted item counts toward at most one answer-key entry: items whose value matches "
    "an entry are paired first, so one quote covering two entries isn't scored twice."
)
