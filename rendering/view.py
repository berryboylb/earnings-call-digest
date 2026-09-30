"""Builds the DigestView: what the one-page digest shows, in the order it shows it.

Only verified items reach the four main tables. Everything comes straight from the
verification result; nothing here is written by an LLM.
"""

from datetime import datetime, timezone

from constants.rendering import (
    BANNER,
    LIMITS_LINE,
    NEEDS_REVIEW_NOTE,
    NONE_IDENTIFIED,
    NOT_AVAILABLE,
    POSSIBLY_MISSED_NOTE,
    QA_NOTE,
    TRUST_LINE,
)
from schema.digest import DigestMeta, DigestView, Table
from schema.verification import VerificationResult, VerifiedItem


def build_view(result: VerificationResult, meta: DigestMeta, generated_at: datetime | None = None) -> DigestView:
    verified = [item for item in result.items if item.status == "verified"]
    needs_review = [item for item in result.items if item.status == "unverified"]
    failed_sections = [name for name, status in result.section_status.items() if status == "failed"]

    def of_kind(kind: str) -> list[VerifiedItem]:
        return [item for item in verified if item.kind == kind]

    def empty_text(depends_on: list[str]) -> str:
        if any(section in failed_sections for section in depends_on):
            return NOT_AVAILABLE
        return NONE_IDENTIFIED

    both_sections = ["prepared", "qa"]
    tables = [
        Table(
            title="Headline figures",
            headers=["Metric", "Value", "Period", "Basis", "Said by", "Src"],
            rows=[[f["metric"], f["value"], f["period"], f["basis"], item.speaker, sources(item)]
                  for item, f in _with_fields(of_kind("figure"))],
            empty_text=empty_text(both_sections),
        ),
        Table(
            title="Guidance",
            headers=["Metric", "Range", "Period", "Direction", "Said by", "Src"],
            rows=[[f["metric"], f["range"], f["period"], f["direction"], item.speaker, sources(item)]
                  for item, f in _with_fields(of_kind("guidance"))],
            empty_text=empty_text(both_sections),
        ),
        Table(
            title="Risks & hedging",
            headers=["Theme", "Language used", "Said by", "Src"],
            rows=[[f["theme"], f["hedging_phrase"], item.speaker, sources(item)]
                  for item, f in _with_fields(of_kind("risk"))],
            empty_text=empty_text(both_sections),
        ),
        Table(
            title="Q&A: what analysts pushed on",
            headers=["Topic", "Asked by", "Response", "Answered by", "Src"],
            rows=[[f["topic"], f["asked_by"], f["answer_quality"], item.speaker, sources(item)]
                  for item, f in _with_fields(of_kind("qa"))],
            empty_text=empty_text(["qa"]),
            note=QA_NOTE,
        ),
        Table(
            title="Needs review",
            headers=["ID", "Item", "Why it failed"],
            rows=[[item.id, _describe(item), "; ".join(item.reasons)] for item in needs_review],
            empty_text=empty_text(both_sections),
            note=NEEDS_REVIEW_NOTE,
        ),
        Table(
            title="Possibly missed",
            headers=["Src", "Said by", "Number", "Context"],
            rows=[[missed.segment_id, missed.speaker, missed.raw, missed.context]
                  for missed in result.possibly_missed],
            empty_text=NONE_IDENTIFIED,  # found by code from the transcript, not by extraction
            note=POSSIBLY_MISSED_NOTE,
        ),
    ]

    return DigestView(
        title=_title(meta),
        subtitle=f"Call date {meta.call_date} · Source: {meta.source}",
        banner=BANNER.format(sections=" and ".join(failed_sections)) if failed_sections else None,
        trust_line=TRUST_LINE.format(
            verified=len(verified),
            total=len(result.items),
            needs_review=len(needs_review),
            missed=len(result.possibly_missed),
        ),
        tables=tables,
        footer=_footer(meta, generated_at or datetime.now(timezone.utc)),
        limits=LIMITS_LINE,
    )


def sources(item: VerifiedItem) -> str:
    """The segments the evidence comes from: the quote's segment, then any context segments ("S17+S15")."""
    segment_ids = []
    for match in [item.source, *item.context]:
        if match is not None and match.segment_id not in segment_ids:
            segment_ids.append(match.segment_id)
    return "+".join(segment_ids)


def _with_fields(items: list[VerifiedItem]) -> list[tuple[VerifiedItem, dict]]:
    return [(item, item.fields) for item in items]


def _describe(item: VerifiedItem) -> str:
    fields = item.fields
    if item.kind == "figure":
        return f"Figure: {fields['metric']} {fields['value']} ({fields['period']})"
    if item.kind == "guidance":
        return f"Guidance: {fields['metric']} {fields['range']} ({fields['period']})"
    if item.kind == "risk":
        return f"Risk: {fields['theme']}"
    return f"Q&A: {fields['topic']}"


def _title(meta: DigestMeta) -> str:
    company = f"{meta.company} ({meta.ticker})" if meta.ticker else meta.company
    return f"{company} · {meta.quarter} earnings call"


def _footer(meta: DigestMeta, generated_at: datetime) -> str:
    parts = [
        f"model {meta.model}",
        f"prompt {meta.prompt_version}",
        f"structured output {meta.structured_output_mode}",
    ]
    if meta.replayed:
        parts.append("replayed from cache")
    parts.append(f"transcript sha256 {meta.transcript_sha256}")
    parts.append(f"generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    return " · ".join(parts)
