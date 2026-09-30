"""Small helpers for cleaning and splitting text."""

from constants.parsing import BYTE_ORDER_MARK, NBSP_CHARS, SENTENCE_BREAK


def normalise_text(text: str) -> str:
    """Make line endings and spaces consistent, so every file looks the same to the parser."""
    text = text.replace(BYTE_ORDER_MARK, "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for special_space in NBSP_CHARS:
        text = text.replace(special_space, " ")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines)


def split_sentences(text: str) -> list[tuple[int, int]]:
    """Return the (start, end) position of each sentence in the text."""
    sentences = []
    start = 0
    for sentence_break in SENTENCE_BREAK.finditer(text):
        end = sentence_break.start("gap")
        sentences.append((start, end))
        start = sentence_break.end("gap")
    if start < len(text):
        sentences.append((start, len(text)))
    return sentences


def matches_any(text: str, patterns: list) -> bool:
    """True if any of the regex patterns is found in the text."""
    for pattern in patterns:
        if pattern.search(text):
            return True
    return False
