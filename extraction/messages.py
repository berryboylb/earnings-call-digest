"""Builds the message the LLM reads for one section of the call."""

from constants.prompts import (
    PRECEDING_CONTEXT_INSTRUCTION,
    SECTION_HEADERS,
    TRANSCRIPT_TAG,
)
from parsing.paragraphs import segment_text
from schema.extraction import SectionName
from schema.transcript import Segment


def build_user_message(
    section: SectionName, segments: list[Segment], preceding_context: list[Segment] | None = None
) -> str:
    """The section's instructions, then its segments inside <transcript> tags.

    preceding_context: text from just before these segments, given only so the model knows
    which period or topic they are about. It goes in its own tags, with an instruction not
    to extract anything from it.
    """
    parts = [SECTION_HEADERS[section]]
    if preceding_context:
        context = "\n\n".join(render_segments(preceding_context))
        parts.append(f"<preceding_context>\n{context}\n</preceding_context>\n{PRECEDING_CONTEXT_INSTRUCTION}")
    body = "\n\n".join(render_segments(segments))
    parts.append(f"<transcript>\n{body}\n</transcript>")
    return "\n\n".join(parts)


def render_segments(segments: list[Segment]) -> list[str]:
    """Each segment as "[S4 | Priya Raman | management]" followed by its text.

    Boilerplate is left out, and so are segments with nothing else in them. Any
    <transcript> tags inside the text are removed, so the text can't end the
    transcript block early.
    """
    blocks = []
    for segment in segments:
        text = TRANSCRIPT_TAG.sub("", segment_text(segment)).strip()
        if text:
            blocks.append(f"[{segment.id} | {segment.speaker} | {segment.role}]\n{text}")
    return blocks
