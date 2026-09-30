"""Splitting a turn into paragraphs and marking safe-harbor boilerplate."""

from __future__ import annotations

from .models import Paragraph, Segment
from .patterns import BOILERPLATE_EXTENDERS, BOILERPLATE_PATTERNS, SENTENCE_BREAK


def split_sentences(text: str) -> list[tuple[int, int]]:
    """(start, end) offsets of each sentence in `text`, without the whitespace between them."""
    spans, start = [], 0
    for m in SENTENCE_BREAK.finditer(text):
        spans.append((start, m.start("gap")))
        start = m.end("gap")
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def _boilerplate_spans(text: str) -> list[tuple[int, int]]:
    """The boilerplate part of a paragraph, as at most one (start, end) span.

    A paragraph has boilerplate if 2 or more patterns match it (extenders don't
    count). The span runs from the first sentence matching a pattern to the last
    sentence matching a pattern or an extender, inclusive; sentences outside that
    run are not boilerplate.
    """
    if sum(bool(p.search(text)) for p in BOILERPLATE_PATTERNS) < 2:
        return []
    sentences = split_sentences(text)
    starts = [(s, e) for s, e in sentences if _matches(text[s:e], BOILERPLATE_PATTERNS)]
    if not starts:
        return []
    ends = [
        (s, e) for s, e in sentences
        if _matches(text[s:e], BOILERPLATE_PATTERNS) or _matches(text[s:e], BOILERPLATE_EXTENDERS)
    ]
    return [(starts[0][0], ends[-1][1])]


def _matches(sentence: str, patterns: list) -> bool:
    return any(p.search(sentence) for p in patterns)


def split_paragraphs(lines: list[str]) -> list[Paragraph]:
    paragraphs, buf = [], []
    for line in [*lines, ""]:
        if line:
            buf.append(line)
        elif buf:
            text = " ".join(buf)
            paragraphs.append(Paragraph(text, _boilerplate_spans(text)))
            buf = []
    return paragraphs


def _without_boilerplate(paragraph: Paragraph) -> str:
    kept, pos = [], 0
    for s, e in paragraph.boilerplate_spans:
        kept.append(paragraph.text[pos:s])
        pos = e
    kept.append(paragraph.text[pos:])
    return " ".join(part.strip() for part in kept if part.strip())


def segment_text(segment: Segment, include_boilerplate: bool = False) -> str:
    """Join a segment's paragraphs with blank lines, leaving out boilerplate unless asked."""
    texts = (p.text if include_boilerplate else _without_boilerplate(p) for p in segment.paragraphs)
    return "\n\n".join(t for t in texts if t)
