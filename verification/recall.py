"""Finds numbers management said that no extracted item covers, for a human to review."""

from constants.verification import MISSED_CONTEXT_CHARS
from schema.verification import Amount, MissedCandidate, VerifiedItem
from utils.numbers import amounts_equal, parse_amounts
from verification.matching import IndexedParagraph, TranscriptIndex


def find_possibly_missed(
    index: TranscriptIndex, items: list[VerifiedItem], section_status: dict[str, str]
) -> list[MissedCandidate]:
    """Every amount in management's words (prepared remarks and Q&A, boilerplate excluded)
    that isn't inside any item's quotes and isn't equal to any extracted value.

    Sections whose extraction failed are skipped: every number in them would look missed,
    and the digest already says that section is not available.
    """
    extracted_values = _extracted_values(items)
    missed = []
    for indexed in index.paragraphs:
        if indexed.segment.role != "management":
            continue
        if section_status.get(indexed.segment.section) == "failed":
            continue
        text = indexed.paragraph.text
        for amount in parse_amounts(text):
            if _in_boilerplate(indexed, amount) or _covered_by_quote(indexed, amount, items):
                continue
            if any(amounts_equal(amount, value) for value in extracted_values):
                continue
            context = text[max(0, amount.start - MISSED_CONTEXT_CHARS):amount.end + MISSED_CONTEXT_CHARS]
            missed.append(MissedCandidate(
                segment_id=indexed.segment.id,
                speaker=indexed.segment.speaker,
                raw=amount.raw,
                context=context.strip(),
            ))
    return missed


def _extracted_values(items: list[VerifiedItem]) -> list[Amount]:
    values = []
    for item in items:
        if item.kind == "figure":
            values += parse_amounts(item.fields["value"])
        if item.kind == "guidance":
            values += parse_amounts(item.fields["range"])
    return values


def _in_boilerplate(indexed: IndexedParagraph, amount: Amount) -> bool:
    for start, end in indexed.paragraph.boilerplate_spans:
        if amount.start < end and amount.end > start:
            return True
    return False


def _covered_by_quote(indexed: IndexedParagraph, amount: Amount, items: list[VerifiedItem]) -> bool:
    for item in items:
        for match in [item.source, *item.context]:
            if match is None:
                continue
            same_paragraph = (match.segment_id, match.paragraph_index) == (indexed.segment.id, indexed.paragraph_index)
            if same_paragraph and match.start <= amount.start and amount.end <= match.end:
                return True
    return False
