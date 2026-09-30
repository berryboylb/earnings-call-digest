"""Turns raw transcript text into speaker segments.

No AI here: later stages check every quote the LLM extracts against these segments.
When the parser isn't sure about something, it adds a warning or raises ParseError.
"""

from pathlib import Path

from parsing.header import header_lines, read_call_date, read_call_title
from parsing.paragraphs import split_paragraphs, uses_blank_lines
from parsing.roster import find_roster_start, find_unrecognised_roster, parse_roster
from parsing.sections import find_qa_start
from parsing.speakers import Turn, assign_roles, split_turns
from parsing.validation import quality_warnings, validate
from schema.transcript import Paragraph, ParsedTranscript, ParseError, Section, Segment
from utils.names import name_key
from utils.text import normalise_text


def parse_file(path: str | Path) -> ParsedTranscript:
    text = Path(path).read_text(encoding="utf-8-sig")
    return parse_transcript(text)


def parse_transcript(text: str) -> ParsedTranscript:
    """Parse transcript text into speaker segments. Raises ParseError if the result can't be trusted."""
    warnings = []
    lines = normalise_text(text).split("\n")

    # 1. The participant list says who is management and who is an analyst.
    participants, body_start = parse_roster(lines)
    if not participants:
        unrecognised_list_warnings, unrecognised_list_end = find_unrecognised_roster(lines)
        warnings += unrecognised_list_warnings
        body_start = max(body_start, unrecognised_list_end)
    roster = {name_key(participant.name): participant for participant in participants}

    # 2. Split the rest of the text into speaker turns.
    turns, turn_warnings = split_turns(lines[body_start:], roster, first_line_no=body_start + 1)
    warnings += turn_warnings
    blank_lines_separate = uses_blank_lines(lines[body_start:])
    turns, paragraphs = _drop_empty_turns(turns, warnings, blank_lines_separate)

    # 3. Mark each turn "prepared" or "qa", and decide each speaker's role.
    sections = _label_sections(turns, warnings)
    roles = assign_roles(turns, sections, roster)

    # 4. Build the segments, then check them.
    segments = []
    for i, turn in enumerate(turns):
        segments.append(Segment(
            id=f"S{i + 1}",
            speaker=turn.speaker,
            role=roles[turn.speaker],
            section=sections[i],
            paragraphs=paragraphs[i],
        ))

    speakers = list(dict.fromkeys(segment.speaker for segment in segments))  # unique, in order
    validate(segments, speakers)
    unknown_speakers = [speaker for speaker in speakers if roles[speaker] == "unknown"]
    warnings += quality_warnings(segments, unknown_speakers, has_participant_list=bool(participants))

    # 5. The header: the lines before the participant list or the first speaker.
    header_end = turns[0].line_no - 1
    roster_start = find_roster_start(lines)
    if roster_start is not None:
        header_end = min(header_end, roster_start)
    header = header_lines(lines, header_end)

    return ParsedTranscript(
        participants=participants,
        segments=segments,
        roster_source="participant_list" if participants else "heuristic",
        unknown_speakers=unknown_speakers,
        warnings=warnings,
        header=header,
        call_title=read_call_title(header),
        call_date=read_call_date(header),
    )


def _drop_empty_turns(
    turns: list[Turn], warnings: list[str], blank_lines_separate: bool
) -> tuple[list[Turn], list[list[Paragraph]]]:
    """Split each turn into paragraphs, and drop turns with no text at all."""
    kept_turns = []
    kept_paragraphs = []
    silent_speakers = []
    for turn in turns:
        paragraphs = split_paragraphs(turn.lines, blank_lines_separate)
        if paragraphs:
            kept_turns.append(turn)
            kept_paragraphs.append(paragraphs)
        else:
            silent_speakers.append(turn.speaker)

    if silent_speakers:
        warnings.append(f"Dropped speaker lines with no text: {', '.join(silent_speakers)}")
    if not kept_turns:
        raise ParseError("No speaker turns found; is this an earnings call transcript?")
    return kept_turns, kept_paragraphs


def _label_sections(turns: list[Turn], warnings: list[str]) -> list[Section]:
    """Mark each turn "prepared" or "qa". Every turn from the start of Q&A on is "qa"."""
    qa_start = find_qa_start(turns)
    if qa_start is None:
        warnings.append("No Q&A section found; all segments marked 'prepared'.")
        qa_start = len(turns)

    sections = []
    for i in range(len(turns)):
        sections.append("qa" if i >= qa_start else "prepared")
    return sections
