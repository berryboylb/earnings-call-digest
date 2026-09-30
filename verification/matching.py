"""Finds where a quote appears in the transcript: exactly, or failing that, fuzzily."""

import re
from collections import Counter
from dataclasses import dataclass

from rapidfuzz import fuzz

from constants.verification import (
    FUZZY_MIN_OVERLAP,
    FUZZY_MIN_TOKENS,
    FUZZY_THRESHOLD,
    FUZZY_WINDOW_SLACK,
)
from schema.transcript import Paragraph, ParsedTranscript, Segment
from schema.verification import SourceMatch
from utils.names import name_key
from utils.text import split_sentences

# A token is a run of characters between spaces, en dashes or em dashes.
TOKEN = re.compile(r"[^\s–—]+")
# A comma between digits, as in "97,000".
THOUSANDS_SEPARATOR = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
STRAIGHT_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


@dataclass
class Token:
    text: str  # lowercased and cleaned, for comparing
    start: int  # position in the original text
    end: int


@dataclass
class IndexedParagraph:
    segment: Segment
    paragraph_index: int
    paragraph: Paragraph
    tokens: list[Token]


class TranscriptIndex:
    """Every paragraph of the transcript, split into tokens, ready to search."""

    def __init__(self, parsed: ParsedTranscript):
        self.parsed = parsed
        self.segments = {segment.id: segment for segment in parsed.segments}
        self.paragraphs = []
        for segment in parsed.segments:
            for i, paragraph in enumerate(segment.paragraphs):
                self.paragraphs.append(IndexedParagraph(segment, i, paragraph, tokenise(paragraph.text)))
        self._by_position = {(p.segment.id, p.paragraph_index): p for p in self.paragraphs}

    def paragraph_of(self, match: SourceMatch) -> IndexedParagraph:
        return self._by_position[(match.segment_id, match.paragraph_index)]

    def segment_of(self, match: SourceMatch) -> Segment:
        return self.segments[match.segment_id]


def tokenise(text: str) -> list[Token]:
    """Split text into tokens for comparing: lowercase, straight quotes, no punctuation at
    either end (except $ and %), and no thousands separators ("97,000" becomes "97000")."""
    tokens = []
    for match in TOKEN.finditer(text):
        start, end = match.start(), match.end()
        while start < end and _is_edge_punctuation(text[start]):
            start += 1
        while end > start and _is_edge_punctuation(text[end - 1]):
            end -= 1
        if start == end:
            continue
        word = text[start:end].lower().translate(STRAIGHT_QUOTES)
        word = THOUSANDS_SEPARATOR.sub("", word)
        tokens.append(Token(word, start, end))
    return tokens


def find_quote(index: TranscriptIndex, quote: str, speaker: str = "") -> SourceMatch | None:
    """Find the quote in the transcript. Returns where it is, or None if it isn't there.

    An exact word-for-word match is tried first, then a fuzzy match (only for quotes
    of at least FUZZY_MIN_TOKENS words). Matches outside safe-harbor boilerplate are
    preferred, then matches in `speaker`'s own segments.
    """
    quote_words = [token.text for token in tokenise(quote)]
    if not quote_words:
        return None

    matches = _exact_matches(index, quote_words)
    if not matches and len(quote_words) >= FUZZY_MIN_TOKENS:
        matches = _fuzzy_matches(index, quote_words)
    if not matches:
        return None

    speaker_key = name_key(speaker)

    def preference(match: SourceMatch) -> tuple:
        other_speaker = name_key(index.segment_of(match).speaker) != speaker_key
        return (match.in_boilerplate, other_speaker, -match.score)

    return min(matches, key=preference)


def sentence_context(text: str, start: int, end: int) -> tuple[int, int]:
    """The start and end of the sentence (or sentences) that contain text[start:end]."""
    overlapping = []
    for sentence_start, sentence_end in split_sentences(text):
        if sentence_start < end and sentence_end > start:
            overlapping.append((sentence_start, sentence_end))
    if not overlapping:
        return start, end
    return overlapping[0][0], overlapping[-1][1]


def _exact_matches(index: TranscriptIndex, quote_words: list[str]) -> list[SourceMatch]:
    matches = []
    size = len(quote_words)
    for indexed in index.paragraphs:
        words = [token.text for token in indexed.tokens]
        for i in range(len(words) - size + 1):
            if words[i:i + size] == quote_words:
                matches.append(_source_match(indexed, i, i + size, "exact", 1.0))
    return matches


def _fuzzy_matches(index: TranscriptIndex, quote_words: list[str]) -> list[SourceMatch]:
    """The best window of words in each paragraph that scores at least FUZZY_THRESHOLD."""
    quote_text = " ".join(quote_words)
    quote_counts = Counter(quote_words)
    needed_overlap = FUZZY_MIN_OVERLAP * len(quote_words)
    smallest = max(1, len(quote_words) - FUZZY_WINDOW_SLACK)
    largest = len(quote_words) + FUZZY_WINDOW_SLACK

    matches = []
    for indexed in index.paragraphs:
        words = [token.text for token in indexed.tokens]
        if _overlap(quote_counts, words) < needed_overlap:
            continue  # the paragraph doesn't share enough words with the quote

        best = None
        for size in range(smallest, largest + 1):
            for i in range(len(words) - size + 1):
                window = words[i:i + size]
                if _overlap(quote_counts, window) < needed_overlap:
                    continue
                score = fuzz.ratio(quote_text, " ".join(window)) / 100
                if score >= FUZZY_THRESHOLD and (best is None or score > best.score):
                    best = _source_match(indexed, i, i + size, "fuzzy", score)
        if best is not None:
            matches.append(best)
    return matches


def _source_match(indexed: IndexedParagraph, first: int, after_last: int, method: str, score: float) -> SourceMatch:
    start = indexed.tokens[first].start
    end = indexed.tokens[after_last - 1].end
    return SourceMatch(
        segment_id=indexed.segment.id,
        paragraph_index=indexed.paragraph_index,
        start=start,
        end=end,
        text=indexed.paragraph.text[start:end],
        method=method,
        score=round(score, 3),
        in_boilerplate=_overlaps_boilerplate(indexed.paragraph, start, end),
    )


def _overlaps_boilerplate(paragraph: Paragraph, start: int, end: int) -> bool:
    for boilerplate_start, boilerplate_end in paragraph.boilerplate_spans:
        if start < boilerplate_end and end > boilerplate_start:
            return True
    return False


def _overlap(quote_counts: Counter, words: list[str]) -> int:
    """How many of the quote's words (counting repeats) appear in `words`."""
    return sum((quote_counts & Counter(words)).values())


def _is_edge_punctuation(character: str) -> bool:
    return not character.isalnum() and character not in "$%"
