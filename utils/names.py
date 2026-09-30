"""Helpers for recognising and comparing people's names."""

from constants.parsing import (
    ABBREVIATION_MAX_LEN,
    CURLY_APOSTROPHE,
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
    """Turn a name into a simple key, so different spellings of one person match.

    "Priya S. Raman" and "PRIYA RAMAN" both become ("priya", "raman"):
    lowercase, no punctuation, and no single-letter initials.
    """
    name = name.lower().replace(CURLY_APOSTROPHE, "'")
    words = NAME_KEY_WORD.findall(name)
    words_without_initials = [word for word in words if len(word) > 1]
    return tuple(words_without_initials)


def looks_like_name(text: str) -> bool:
    """True if the text looks like a person's name, e.g. "Priya S. Raman" or "Ana de la Cruz"."""
    words = text.split()
    if len(words) < NAME_MIN_WORDS or len(words) > NAME_MAX_WORDS:
        return False
    if not words[0][0].isupper():
        return False
    for word in words:
        if not NAME_TOKEN.fullmatch(word):
            return False
        if word.lower().strip(".") in NOT_NAME_WORDS:
            return False
        if not word[0].isupper() and word not in NAME_PARTICLES:
            return False
    return True


def looks_like_title(text: str) -> bool:
    """True if the text looks like a job title or firm ("Chief Financial Officer", "Citi"),
    not the rest of a sentence."""
    words = text.split()
    if not words or len(words) > TITLE_MAX_WORDS:
        return False
    if text.endswith("?") or text.endswith("!"):
        return False
    # "Acme Inc." is a title; "...strong results." is a sentence.
    ends_like_a_sentence = text.endswith(".") and len(words[-1]) > ABBREVIATION_MAX_LEN
    return not ends_like_a_sentence


def split_name_title(line: str) -> tuple[str, str] | None:
    """Split "Jane Doe - Chief Financial Officer" into ("Jane Doe", "Chief Financial Officer").

    Returns None if the line isn't a name followed by a separator and a title.
    """
    parts = NAME_TITLE_SEP.split(line, maxsplit=1)
    if len(parts) != 2:
        return None
    name, title = parts[0].strip(), parts[1].strip()
    if not looks_like_name(name) or not title:
        return None
    return name, title


def contains_words(words: tuple[str, ...], wanted: tuple[str, ...]) -> bool:
    """True if `wanted` appears inside `words` as consecutive words.

    contains_words(("comes", "from", "alex", "chen"), ("alex", "chen")) is True.
    """
    if not wanted:
        return False
    size = len(wanted)
    for start in range(len(words) - size + 1):
        if words[start:start + size] == wanted:
            return True
    return False
