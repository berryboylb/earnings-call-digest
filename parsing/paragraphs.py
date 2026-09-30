"""Splitting a turn into paragraphs and flagging safe-harbor boilerplate."""

from __future__ import annotations

from .models import Paragraph, Segment
from .patterns import BOILERPLATE_PATTERNS


def _is_boilerplate(text: str) -> bool:
    return sum(bool(p.search(text)) for p in BOILERPLATE_PATTERNS) >= 2


def split_paragraphs(lines: list[str]) -> list[Paragraph]:
    paragraphs, buf = [], []
    for line in [*lines, ""]:
        if line:
            buf.append(line)
        elif buf:
            text = " ".join(buf)
            paragraphs.append(Paragraph(text, _is_boilerplate(text)))
            buf = []
    return paragraphs


def segment_text(segment: Segment, include_boilerplate: bool = False) -> str:
    """Join a segment's paragraphs with blank lines, leaving out boilerplate unless asked."""
    return "\n\n".join(
        p.text for p in segment.paragraphs if include_boilerplate or not p.boilerplate
    )
