"""Checks every extracted item against the transcript. Pure code, no LLM."""

from pydantic import BaseModel

from constants.verification import ID_PREFIXES
from schema.extraction import ExtractionRun
from schema.transcript import ParsedTranscript
from schema.verification import ItemKind, VerificationResult, VerifiedItem
from verification.checks import (
    check_asked_by,
    check_boilerplate,
    check_context,
    check_direction,
    check_guidance_period,
    check_hedging_phrase,
    check_is_comparison,
    check_prior_period,
    check_quote_found,
    check_speaker,
    check_values,
)
from verification.dedupe import merge_duplicates
from verification.matching import TranscriptIndex
from verification.recall import find_possibly_missed

# Each kind of item, and the Extraction field it comes from.
ITEM_LISTS = [("figure", "figures"), ("guidance", "guidance"), ("risk", "risks"), ("qa", "qa_topics")]


def verify_run(parsed: ParsedTranscript, run: ExtractionRun) -> VerificationResult:
    """Verify every item from the sections that extracted successfully."""
    index = TranscriptIndex(parsed)

    items = []
    for section in run.sections:
        if section.status not in ("ok", "partial"):
            continue  # its status is passed on, so later stages can say it's not available
        for kind, list_name in ITEM_LISTS:
            for extracted in getattr(section.extraction, list_name):
                items.append(verify_item(kind, extracted, section.name, index))

    items = merge_duplicates(items)
    assign_ids(items)
    section_status = {section.name: section.status for section in run.sections}
    not_extracted = set()  # segments whose extraction call failed
    for section in run.sections:
        not_extracted.update(section.failed_segments)
    possibly_missed = find_possibly_missed(index, items, section_status, not_extracted)

    failed_calls = {section.name: section.failed_calls for section in run.sections if section.failed_calls}
    return VerificationResult(items=items, possibly_missed=possibly_missed, section_status=section_status,
                              failed_calls=failed_calls)


def verify_item(kind: ItemKind, extracted: BaseModel, origin: str, index: TranscriptIndex) -> VerifiedItem:
    """Run the checks for this kind of item. Any reason makes it unverified."""
    fields = extracted.model_dump()
    item = VerifiedItem(kind=kind, fields=fields, speaker_claimed=fields["speaker"], origin=origin)

    if check_quote_found(item, index):
        check_boilerplate(item)
        check_speaker(item, index)
        if kind == "figure":
            check_context(item, index)
            check_values(item, index)
            check_prior_period(item, index)
            check_is_comparison(item)
        if kind == "guidance":
            check_context(item, index)
            check_values(item, index)
            check_direction(item, index)
            check_guidance_period(item, index)
        if kind == "risk":
            check_hedging_phrase(item, index)
        if kind == "qa":
            check_asked_by(item, index)

    item.update_status()
    return item


def assign_ids(items: list[VerifiedItem]) -> None:
    """Number the items per kind, in extraction order: F1, F2... G1... R1... Q1..."""
    counts = {}
    for item in items:
        counts[item.kind] = counts.get(item.kind, 0) + 1
        item.id = f"{ID_PREFIXES[item.kind]}{counts[item.kind]}"
