"""Stage 1: split a raw earnings call transcript into speaker segments.

No AI here. Later stages check every extracted quote against these segments, so the
parser has to be explicit about WHO said WHAT and in WHICH section. When it can't be
sure, it adds a warning or raises ParseError. It never guesses silently.

Usage:
    uv run python -m parse data/<file>.txt
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Role = Literal["management", "analyst", "operator", "unknown"]
Section = Literal["prepared", "qa"]

MIN_WORDS = 1500
OPERATOR = "Operator"


class ParseError(Exception):
    """Raised when a transcript can't be turned into a trustworthy result."""


@dataclass
class Participant:
    name: str
    title: str
    role: Role


@dataclass
class Paragraph:
    text: str
    boilerplate: bool = False


@dataclass
class Segment:
    id: str
    speaker: str
    role: Role
    section: Section
    paragraphs: list[Paragraph] = field(default_factory=list)


@dataclass
class ParsedTranscript:
    participants: list[Participant]
    segments: list[Segment]
    roster_source: Literal["participant_list", "heuristic"]
    unknown_speakers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# --- Patterns ---------------------------------------------------------------

# Participant-list headers (matched against the whole line, minus a trailing colon).
_MANAGEMENT_HEADER = re.compile(r"(?:company|corporate)\s+participants|executives", re.I)
_ANALYST_HEADER = re.compile(r"(?:conference\s+call|other)\s+participants|analysts", re.I)

# Separator between a name and its title: a spaced hyphen, double hyphen, en dash or
# em dash, or a comma. Examples: "Jane Doe - CFO", "Jane Doe – CFO", "Jane Doe, CFO".
_NAME_TITLE_SEP = re.compile(r"\s+(?:--?|–|—)\s+|,\s+")

# "Operator" alone on a line, or "Operator:" followed by inline text.
_OPERATOR_LINE = re.compile(r"operator\s*(?::\s*(?P<text>.*))?", re.I)

# Layout B: "Name: text". The name part (up to 60 chars, no colon) is validated separately.
_INLINE_SPEAKER = re.compile(r"(?P<name>[^:]{1,60}?)\s*:\s+(?P<text>\S.*)")

# Generic labels some transcripts use for people they couldn't identify.
_UNIDENTIFIED = re.compile(
    r"unidentified\s+(?:analyst|participant|speaker|company\s+representative)", re.I
)

# One word of a person's name: letters plus inner . ' ’ - ("S.", "O'Neil", "Jean-Luc").
_NAME_TOKEN = re.compile(r"[^\W\d_](?:[^\W\d_]|['’.\-])*")
_NAME_PARTICLES = {"de", "da", "di", "du", "del", "della", "van", "von", "der", "den", "la", "le", "bin", "al"}
# Capitalised words that show up in headings and greetings but never in a person's name.
_NOT_NAME_WORDS = {
    "call", "conference", "earnings", "participants", "session", "remarks", "quarter",
    "results", "transcript", "presentation", "question", "questions", "answer",
    "answers", "operator", "instructions", "executives", "analysts", "thank", "thanks",
    "you", "good", "morning", "afternoon", "evening", "welcome", "everyone", "hello",
    "closing", "opening", "prepared", "company", "corporate", "fiscal", "financial",
    "highlights", "overview", "outlook", "guidance", "disclaimer", "statements",
}

# An explicit Q&A header on its own line: "Question-and-Answer Session",
# "Questions and Answers", "Q&A", "Q & A Session".
_QA_HEADER = re.compile(
    r"(?:questions?[\s-]+(?:and|&)[\s-]+answers?|q\s*&\s*a)(?:\s+session)?\s*:?", re.I
)

# Operator wording that opens Q&A: "question-and-answer", "Q&A", "first question",
# "open the line(s)/floor/call for/to questions".
_QA_START_PHRASES = re.compile(
    r"question[\s-]+and[\s-]+answer|\bq\s*&\s*a\b|first question"
    r"|open(?:\s+up)?\s+the\s+(?:lines?|floor|call)\s+(?:for|to)\s+questions",
    re.I,
)

# Safe-harbor language. A paragraph is boilerplate if it matches 2 or more of these.
_BOILERPLATE_PATTERNS = [
    re.compile(r"forward[\s-]+looking\s+statements?", re.I),
    re.compile(r"safe\s+harbou?r", re.I),
    re.compile(r"risks?\s+and\s+uncertaint", re.I),
    # "could differ materially", or "may cause actual results to differ materially"
    re.compile(r"\b(?:could|may|might)\b[^.]{0,60}?\bdiffer\s+materially", re.I),
    re.compile(r"private\s+securities\s+litigation\s+reform\s+act", re.I),
    # "non-GAAP ... reconciliation" in either order, within one paragraph
    re.compile(r"non-gaap.*reconcil|reconcil.*non-gaap", re.I),
]

# The end of a sentence: . ! ? or …, optionally followed by closing quotes or brackets.
_SENTENCE_END = re.compile(r"[.!?…][\"'’”)\]]*$")


# --- Name helpers -----------------------------------------------------------

def _name_key(name: str) -> tuple[str, ...]:
    """A comparison key that ignores case, punctuation and initials.

    "Priya S. Raman" and "PRIYA RAMAN" both become ("priya", "raman").
    """
    words = re.findall(r"[^\W\d_]+(?:['-][^\W\d_]+)*", name.lower().replace("’", "'"))
    return tuple(w for w in words if len(w) > 1)


def _looks_like_name(text: str) -> bool:
    """True for 2-5 capitalised name-like words, e.g. "Priya S. Raman" or "Ana de la Cruz"."""
    words = text.split()
    if not 2 <= len(words) <= 5 or not words[0][:1].isupper():
        return False
    for w in words:
        if not _NAME_TOKEN.fullmatch(w) or w.lower().strip(".") in _NOT_NAME_WORDS:
            return False
        if not (w[0].isupper() or w in _NAME_PARTICLES):
            return False
    return True


def _looks_like_title(text: str) -> bool:
    """A job title or firm name, not the rest of a sentence (short, and no sentence ending)."""
    words = text.split()
    if not words or len(words) > 12 or text.endswith(("?", "!")):
        return False
    # Allow abbreviations like "Inc." or "Co.", but not a sentence ending "...results."
    return not (text.endswith(".") and len(words[-1]) > 4)


def _split_name_title(line: str) -> tuple[str, str] | None:
    parts = _NAME_TITLE_SEP.split(line, maxsplit=1)
    if len(parts) == 2 and _looks_like_name(parts[0]) and parts[1].strip():
        return parts[0].strip(), parts[1].strip()
    return None


def _contains(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    n = len(needle)
    return n > 0 and any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


# --- Parsing steps ----------------------------------------------------------

def _normalise(text: str) -> str:
    text = text.replace("﻿", "").replace("\r\n", "\n").replace("\r", "\n")
    for nbsp in (" ", " ", " "):
        text = text.replace(nbsp, " ")
    return "\n".join(line.rstrip() for line in text.split("\n"))


def _parse_roster(lines: list[str]) -> tuple[list[Participant], int]:
    """Read the participant list. Returns (participants, index of the first line after it).

    The block begins at a known header, and must come before the first Operator
    line. It ends at the first line that isn't a header, an entry or a blank line.
    It also ends at a repeated name, because that line is the first speaker line
    ("Jane Doe - CFO").
    """
    participants: list[Participant] = []
    seen: set[tuple[str, ...]] = set()
    role: Role | None = None
    last = -1
    for i, raw in enumerate(lines):
        line = raw.strip()
        header = line.removesuffix(":").strip()
        if _MANAGEMENT_HEADER.fullmatch(header):
            role, last = "management", i
            continue
        if _ANALYST_HEADER.fullmatch(header):
            role, last = "analyst", i
            continue
        if role is None:
            if _OPERATOR_LINE.fullmatch(line):
                break  # the call has started and there was no participant list
            continue
        if not line:
            continue
        entry = _split_name_title(line)
        if entry is None or _name_key(entry[0]) in seen:
            break
        seen.add(_name_key(entry[0]))
        participants.append(Participant(entry[0], entry[1], role))
        last = i
    return participants, last + 1


@dataclass
class _Turn:
    speaker: str
    after_qa_header: bool
    lines: list[str] = field(default_factory=list)


def _layout_a_names(line: str) -> list[str]:
    """Possible speaker names for a line that is only a name: "Name", "Name:" or "Name - Title"."""
    names = [line.removesuffix(":").strip()]
    split = _split_name_title(line)
    if split and _looks_like_title(split[1]):
        names.append(split[0])
    return names


def _count_labels(lines: list[str]) -> Counter:
    """Count how often each name-like label shows up as a possible speaker line."""
    counts: Counter = Counter()
    for raw in lines:
        line = raw.strip()
        names = _layout_a_names(line)
        if m := _INLINE_SPEAKER.fullmatch(line):
            names.append(m["name"])
        for key in {_name_key(n) for n in names if _looks_like_name(n)}:
            counts[key] += 1
    return counts


def _accept_name(name: str, roster: dict, counts: Counter, current: _Turn | None) -> str | None:
    """Return the speaker label if `name` is a speaker, else None.

    A name in the roster is always accepted. A name that isn't in the roster needs
    evidence that it really is a speaker: it appears as a label at least twice, or
    the turn in progress mentions it ("...comes from Alex Chen with Citi",
    "over to Marcus").
    """
    name = name.strip()
    key = _name_key(name)
    if key in roster:
        return roster[key].name
    if _UNIDENTIFIED.fullmatch(name):
        return name
    if not _looks_like_name(name) or not key:
        return None
    if counts[key] >= 2:
        return name
    if current is not None:
        said = _name_key(" ".join(current.lines))
        if _contains(said, key) or key[0] in said:
            return name
    return None


def _match_speaker(line: str, roster: dict, counts: Counter, current: _Turn | None):
    """If `line` starts a new turn, return (speaker, inline text). Otherwise return None."""
    if m := _OPERATOR_LINE.fullmatch(line):
        return OPERATOR, (m["text"] or "").strip()
    for name in _layout_a_names(line):
        if label := _accept_name(name, roster, counts, current):
            return label, ""
    if (m := _INLINE_SPEAKER.fullmatch(line)) and (
        label := _accept_name(m["name"], roster, counts, current)
    ):
        return label, m["text"].strip()
    return None


def _looks_like_label(line: str) -> bool:
    """True if `line` has the shape of a speaker line, whether or not it was accepted."""
    names = _layout_a_names(line)
    if m := _INLINE_SPEAKER.fullmatch(line):
        names.append(m["name"])
    return any(_looks_like_name(n.strip()) for n in names)


def _split_turns(lines: list[str], roster: dict, first_line_no: int) -> tuple[list[_Turn], list[str]]:
    """Split body lines into turns. `first_line_no` is the file line number of lines[0], used in warnings."""
    counts = _count_labels(lines)
    canonical: dict[tuple[str, ...], str] = {}  # first spelling seen for each speaker
    turns: list[_Turn] = []
    warnings: list[str] = []
    qa_header_seen = False
    for line_no, raw in enumerate(lines, start=first_line_no):
        line = raw.strip()
        if _QA_HEADER.fullmatch(line):
            qa_header_seen = True
            continue
        current = turns[-1] if turns else None
        match = _match_speaker(line, roster, counts, current) if line else None
        if match:
            speaker, inline = match
            speaker = canonical.setdefault(_name_key(speaker), speaker)
            turns.append(_Turn(speaker, qa_header_seen, [inline] if inline else []))
        elif current is not None:
            if line and _looks_like_label(line):
                warnings.append(
                    f"Possible speaker line not recognised: '{line}' (line {line_no}), "
                    f"text attributed to {current.speaker}"
                )
            current.lines.append(line)
        # Text before the first speaker (title lines) is ignored.
    return turns, warnings


def _is_boilerplate(text: str) -> bool:
    return sum(bool(p.search(text)) for p in _BOILERPLATE_PATTERNS) >= 2


def _paragraphs(lines: list[str]) -> list[Paragraph]:
    paragraphs, buf = [], []
    for line in [*lines, ""]:
        if line:
            buf.append(line)
        elif buf:
            text = " ".join(buf)
            paragraphs.append(Paragraph(text, _is_boilerplate(text)))
            buf = []
    return paragraphs


def _find_qa_start(turns: list[_Turn]) -> int | None:
    """Index of the first Q&A turn, or None.

    Q&A starts at an explicit header, or at the first Operator turn that uses
    opening-Q&A wording, whichever comes first. The Operator turn only counts
    after someone else has spoken, because the Operator's welcome often says
    "there will be a question-and-answer session later".
    """
    header = next((i for i, t in enumerate(turns) if t.after_qa_header), None)
    handoff, someone_spoke = None, False
    for i, t in enumerate(turns):
        if t.speaker != OPERATOR:
            someone_spoke = True
        elif someone_spoke and _QA_START_PHRASES.search(" ".join(t.lines)):
            handoff = i
            break
    found = [i for i in (header, handoff) if i is not None]
    return min(found) if found else None


def _introduced_as_questioner(speaker: str, turns: list[_Turn], sections: list[Section]) -> bool:
    """True if an Operator Q&A hand-off names `speaker` and they speak next."""
    key = _name_key(speaker)
    for prev, turn, section in zip(turns, turns[1:], sections[1:]):
        if turn.speaker == speaker and section == "qa" and prev.speaker == OPERATOR:
            text = " ".join(prev.lines)
            if "question" in text.lower() and _contains(_name_key(text), key):
                return True
    return False


def _assign_roles(turns: list[_Turn], sections: list[Section], roster: dict) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for turn in turns:
        s = turn.speaker
        if s in roles:
            continue
        if s == OPERATOR:
            roles[s] = "operator"
        elif _name_key(s) in roster:
            roles[s] = roster[_name_key(s)].role
        elif _UNIDENTIFIED.fullmatch(s):
            roles[s] = "analyst" if "analyst" in s.lower() else "unknown"
        elif roster:
            roles[s] = "unknown"  # a participant list exists, so roles come only from it
        elif _introduced_as_questioner(s, turns, sections):
            roles[s] = "analyst"
        elif any(t.speaker == s and sec == "prepared" for t, sec in zip(turns, sections)):
            roles[s] = "management"
        else:
            roles[s] = "unknown"
    return roles


# --- Public API -------------------------------------------------------------

def parse_transcript(text: str) -> ParsedTranscript:
    """Parse transcript text into speaker segments. Raises ParseError if the result can't be trusted."""
    lines = _normalise(text).split("\n")
    participants, body_start = _parse_roster(lines)
    roster = {_name_key(p.name): p for p in participants}
    turns, warnings = _split_turns(lines[body_start:], roster, first_line_no=body_start + 1)
    silent = [t.speaker for t in turns if not _paragraphs(t.lines)]
    if silent:
        warnings.append(f"Dropped speaker lines with no text: {', '.join(silent)}")
        turns = [t for t in turns if _paragraphs(t.lines)]
    if not turns:
        raise ParseError("No speaker turns found; is this an earnings call transcript?")

    qa_start = _find_qa_start(turns)
    if qa_start is None:
        warnings.append("No Q&A section found; all segments marked 'prepared'.")
        qa_start = len(turns)
    sections: list[Section] = ["qa" if i >= qa_start else "prepared" for i in range(len(turns))]
    roles = _assign_roles(turns, sections, roster)

    segments = [
        Segment(f"S{i + 1}", t.speaker, roles[t.speaker], sections[i], _paragraphs(t.lines))
        for i, t in enumerate(turns)
    ]

    speakers = list(dict.fromkeys(s.speaker for s in segments))
    if len(speakers) < 2:
        raise ParseError(f"Only {len(speakers)} distinct speaker found; need at least 2.")
    if len(segments) < 3:
        raise ParseError(f"Only {len(segments)} segments found; need at least 3.")
    if not any(s.role == "management" for s in segments):
        raise ParseError("No management speaker identified.")

    unknown = [s for s in speakers if roles[s] == "unknown"]
    if unknown:
        warnings.append(f"Could not determine role for: {', '.join(unknown)}")
    if not participants:
        warnings.append("No participant list found; roles inferred heuristically.")
    words = sum(len(p.text.split()) for s in segments for p in s.paragraphs)
    if words < MIN_WORDS:
        warnings.append(f"Transcript is short ({words:,} words < {MIN_WORDS:,}); it may be incomplete.")
    last = segments[-1].paragraphs[-1].text
    if not _SENTENCE_END.search(last):
        warnings.append(f"Last paragraph ends mid-sentence ('...{last[-40:]}'); transcript may be truncated.")
    if not any(s.role == "analyst" and s.section == "qa" for s in segments):
        warnings.append("No analyst turns found in Q&A.")

    return ParsedTranscript(
        participants=participants,
        segments=segments,
        roster_source="participant_list" if participants else "heuristic",
        unknown_speakers=unknown,
        warnings=warnings,
    )


def parse_file(path: str | Path) -> ParsedTranscript:
    return parse_transcript(Path(path).read_text(encoding="utf-8-sig"))


def segment_text(segment: Segment, include_boilerplate: bool = False) -> str:
    """Join a segment's paragraphs with blank lines, leaving out boilerplate unless asked."""
    return "\n\n".join(
        p.text for p in segment.paragraphs if include_boilerplate or not p.boilerplate
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m parse <transcript.txt>", file=sys.stderr)
        return 2
    try:
        result = parse_file(args[0])
    except (OSError, ParseError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"roster_source: {result.roster_source}")
    width = max(len(s.speaker) for s in result.segments)
    for s in result.segments:
        markers = "".join("B" if p.boilerplate else "." for p in s.paragraphs)
        print(f"{s.id:<4} {s.speaker:<{width}}  {s.role:<10}  {s.section:<8}  {markers}")
    print(f"warnings ({len(result.warnings)}):")
    for w in result.warnings:
        print(f"  - {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
