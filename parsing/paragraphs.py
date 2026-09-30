"""Splits a turn into paragraphs, and marks the safe-harbor boilerplate inside them."""

from constants.parsing import (
    BOILERPLATE_EXTENDERS,
    BOILERPLATE_MIN_MATCHES,
    BOILERPLATE_PATTERNS,
)
from schema.transcript import Paragraph, Segment
from utils.text import matches_any, split_sentences


def split_paragraphs(lines: list[str]) -> list[Paragraph]:
    """Group lines into paragraphs. A blank line ends a paragraph."""
    paragraphs = []
    current_lines = []
    for line in lines + [""]:  # the extra blank line closes the last paragraph
        if line:
            current_lines.append(line)
        elif current_lines:
            text = " ".join(current_lines)
            paragraphs.append(Paragraph(text, _find_boilerplate(text)))
            current_lines = []
    return paragraphs


def segment_text(segment: Segment, include_boilerplate: bool = False) -> str:
    """The segment's text, with a blank line between paragraphs.
    Boilerplate is left out unless include_boilerplate is True."""
    texts = []
    for paragraph in segment.paragraphs:
        text = paragraph.text if include_boilerplate else _text_without_boilerplate(paragraph)
        if text:
            texts.append(text)
    return "\n\n".join(texts)


def _find_boilerplate(text: str) -> list[tuple[int, int]]:
    """Find the safe-harbor boilerplate in a paragraph, as at most one (start, end) span.

    A paragraph has boilerplate only if at least BOILERPLATE_MIN_MATCHES safe-harbor
    patterns appear in it. The boilerplate then runs from the first sentence that
    matches a pattern to the last sentence that matches a pattern or an extender
    ("Please see our filings..."). Sentences outside that run stay visible.
    """
    patterns_found = sum(1 for pattern in BOILERPLATE_PATTERNS if pattern.search(text))
    if patterns_found < BOILERPLATE_MIN_MATCHES:
        return []

    first_start = None
    last_end = None
    for start, end in split_sentences(text):
        sentence = text[start:end]
        if matches_any(sentence, BOILERPLATE_PATTERNS):
            if first_start is None:
                first_start = start
            last_end = end
        elif matches_any(sentence, BOILERPLATE_EXTENDERS):
            last_end = end

    if first_start is None:
        return []
    return [(first_start, last_end)]


def _text_without_boilerplate(paragraph: Paragraph) -> str:
    kept_parts = []
    position = 0
    for start, end in paragraph.boilerplate_spans:
        kept_parts.append(paragraph.text[position:start])
        position = end
    kept_parts.append(paragraph.text[position:])
    kept_parts = [part.strip() for part in kept_parts if part.strip()]
    return " ".join(kept_parts)
