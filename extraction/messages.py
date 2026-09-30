"""Builds the message the LLM reads for one section of the call."""

from constants.prompts import SECTION_HEADERS, TRANSCRIPT_TAG
from parsing.paragraphs import segment_text
from schema.extraction import SectionName
from schema.transcript import Segment


def build_user_message(section: SectionName, segments: list[Segment]) -> str:
    """The section's instructions, then its segments inside <transcript> tags."""
    body = "\n\n".join(render_segments(segments))
    return f"{SECTION_HEADERS[section]}\n\n<transcript>\n{body}\n</transcript>"


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
