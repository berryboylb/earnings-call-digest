"""Stage 1 of the Earnings Call Digest: raw transcript -> speaker segments."""

from .models import Paragraph, ParsedTranscript, ParseError, Participant, Role, Section, Segment
from .paragraphs import segment_text
from .parser import parse_file, parse_transcript

__all__ = [
    "Paragraph",
    "ParseError",
    "ParsedTranscript",
    "Participant",
    "Role",
    "Section",
    "Segment",
    "parse_file",
    "parse_transcript",
    "segment_text",
]
