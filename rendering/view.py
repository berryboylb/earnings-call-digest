"""Builds the DigestView: what the one-page digest shows, in the order it shows it.

Only verified items reach the four main tables. Everything comes straight from the
verification result; nothing here is written by an LLM.
"""

import re
from datetime import datetime, timezone

from constants.rendering import (
    BANNER,
    FIGURE_PRIORITY,
    LIMITS_LINE,
    MAX_HEADLINE_FIGURES,
    MAX_MAIN_RISKS,
    MAX_POSSIBLY_MISSED,
    NEEDS_REVIEW_NOTE,
    NONE_IDENTIFIED,
    NOT_AVAILABLE,
    POSSIBLY_MISSED_NOTE,
    QA_NOTE,
    TRUST_LINE,
)
from schema.digest import DigestMeta, DigestView, Table
from schema.verification import VerificationResult, VerifiedItem
from utils.numbers import parse_amounts


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
    headline_figures, other_figures = _split_headline_figures(of_kind("figure"))
    main_risks = of_kind("risk")[:MAX_MAIN_RISKS]
    other_risks = of_kind("risk")[MAX_MAIN_RISKS:]
    missed_rows, missed_total = _possibly_missed_rows(result)

    tables = [
        Table(
            title="Headline figures",
            headers=FIGURE_HEADERS,
            rows=[_figure_row(item) for item in headline_figures],
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
            headers=RISK_HEADERS,
            rows=[_risk_row(item) for item in main_risks],
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
    ]
    # Verified items that didn't fit in the main tables; left out when there are none.
    if other_figures:
        tables.append(Table(title="Other reported figures", headers=FIGURE_HEADERS,
                            rows=[_figure_row(item) for item in other_figures], empty_text=NONE_IDENTIFIED))
    if other_risks:
        tables.append(Table(title="Other risk language", headers=RISK_HEADERS,
                            rows=[_risk_row(item) for item in other_risks], empty_text=NONE_IDENTIFIED))
    tables += [
        Table(
            title="Needs review",
            headers=["ID", "Item", "Why it failed"],
            rows=[[item.id, _describe(item), "; ".join(item.reasons)] for item in needs_review],
            empty_text=empty_text(both_sections),
            note=NEEDS_REVIEW_NOTE,
        ),
        Table(
            title=_possibly_missed_title(len(missed_rows), missed_total),
            headers=["Src", "Said by", "Number", "Context"],
            rows=missed_rows,
            empty_text=NONE_IDENTIFIED,  # found by code from the transcript, not by extraction
            note=POSSIBLY_MISSED_NOTE,
        ),
    ]

    return DigestView(
        title=meta.call_title,
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


FIGURE_HEADERS = ["Metric", "Value", "Period", "Basis", "Said by", "Src"]
RISK_HEADERS = ["Theme", "Language used", "Said by", "Src"]


def _figure_row(item: VerifiedItem) -> list[str]:
    fields = item.fields
    return [fields["metric"], fields["value"], fields["period"], fields["basis"], item.speaker, sources(item)]


def _risk_row(item: VerifiedItem) -> list[str]:
    return [item.fields["theme"], item.fields["hedging_phrase"], item.speaker, sources(item)]


def _split_headline_figures(figures: list[VerifiedItem]) -> tuple[list[VerifiedItem], list[VerifiedItem]]:
    """The MAX_HEADLINE_FIGURES most important figures (by FIGURE_PRIORITY, then in the order
    they were said), and the rest. Both keep the order they were said in."""
    def importance(i: int) -> tuple[int, int]:
        return _priority(figures[i].fields["metric"]), i

    ranked = sorted(range(len(figures)), key=importance)
    headline = set(ranked[:MAX_HEADLINE_FIGURES])
    return (
        [figure for i, figure in enumerate(figures) if i in headline],
        [figure for i, figure in enumerate(figures) if i not in headline],
    )


def _priority(metric: str) -> int:
    """The index of the FIGURE_PRIORITY group whose keyword matches the metric best (the
    longest match wins); figures that match no keyword come last."""
    best_rank = len(FIGURE_PRIORITY)
    best_length = 0
    for rank, keywords in enumerate(FIGURE_PRIORITY):
        for keyword in keywords:
            if re.search(r"\b" + re.escape(keyword) + r"\b", metric, re.I) and len(keyword) > best_length:
                best_rank, best_length = rank, len(keyword)
    return best_rank


def _possibly_missed_rows(result: VerificationResult) -> tuple[list[list[str]], int]:
    """At most MAX_POSSIBLY_MISSED rows, currency amounts first, otherwise in transcript order.
    Returns (rows, how many there were in total)."""
    def currency_first(missed) -> bool:
        return not any(amount.unit == "currency" for amount in parse_amounts(missed.raw))

    candidates = sorted(result.possibly_missed, key=currency_first)  # keeps transcript order within each group
    rows = [[missed.segment_id, missed.speaker, missed.raw, missed.context]
            for missed in candidates[:MAX_POSSIBLY_MISSED]]
    return rows, len(candidates)


def _possibly_missed_title(shown: int, total: int) -> str:
    if total > shown:
        return f"Possibly missed (showing {shown} of {total})"
    return "Possibly missed"


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
