"""Recognising and comparing people's names."""

from __future__ import annotations

from .patterns import (
    ABBREVIATION_MAX_LEN,
    NAME_KEY_WORD,
    NAME_MAX_WORDS,
    NAME_MIN_WORDS,
    NAME_PARTICLES,
    NAME_TITLE_SEP,
    NAME_TOKEN,
    NOT_NAME_WORDS,
    TITLE_MAX_WORDS,
)


def name_key(name: str) -> tuple[str, ...]:
    """A comparison key that ignores case, punctuation and initials.

    "Priya S. Raman" and "PRIYA RAMAN" both become ("priya", "raman").
    """
    words = NAME_KEY_WORD.findall(name.lower().replace("’", "'"))
    return tuple(w for w in words if len(w) > 1)


def looks_like_name(text: str) -> bool:
    """True for 2-5 capitalised name-like words, e.g. "Priya S. Raman" or "Ana de la Cruz"."""
    words = text.split()
    if not NAME_MIN_WORDS <= len(words) <= NAME_MAX_WORDS or not words[0][:1].isupper():
        return False
    for w in words:
        if not NAME_TOKEN.fullmatch(w) or w.lower().strip(".") in NOT_NAME_WORDS:
            return False
        if not (w[0].isupper() or w in NAME_PARTICLES):
            return False
    return True


def looks_like_title(text: str) -> bool:
    """A job title or firm name, not the rest of a sentence (short, and no sentence ending)."""
    words = text.split()
    if not words or len(words) > TITLE_MAX_WORDS or text.endswith(("?", "!")):
        return False
    # Allow abbreviations like "Inc." or "Co.", but not a sentence ending "...results."
    return not (text.endswith(".") and len(words[-1]) > ABBREVIATION_MAX_LEN)


def split_name_title(line: str) -> tuple[str, str] | None:
    parts = NAME_TITLE_SEP.split(line, maxsplit=1)
    if len(parts) == 2 and looks_like_name(parts[0]) and parts[1].strip():
        return parts[0].strip(), parts[1].strip()
    return None


def contains(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    n = len(needle)
    return n > 0 and any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))
