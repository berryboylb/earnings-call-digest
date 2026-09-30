"""Small hand-built items and answer keys for the evaluation tests."""

from schema.evaluation import AnswerKey
from schema.verification import (
    MissedCandidate,
    SourceMatch,
    VerificationResult,
    VerifiedItem,
)


def span(text, segment_id="S4"):
    return SourceMatch(segment_id=segment_id, paragraph_index=0, start=0, end=len(text), text=text,
                       method="exact", score=1.0, in_boilerplate=False)


def figure(item_id, value, source_text, period="Q2 2026", basis="not stated", status="verified",
           reasons=(), context_texts=()):
    return VerifiedItem(
        id=item_id, kind="figure", status=status, reasons=list(reasons),
        fields={"metric": "Metric", "value": value, "period": period, "basis": basis,
                "is_comparison": False, "speaker": "Priya Shah", "quote": source_text, "context_quotes": []},
        speaker_claimed="Priya Shah", speaker="Priya Shah", source=span(source_text),
        context=[span(text, "S15") for text in context_texts], origin="prepared",
    )


def guidance(item_id, range_, source_text, period="Q3 2026", direction="not stated", context_texts=()):
    return VerifiedItem(
        id=item_id, kind="guidance",
        fields={"metric": "Revenue", "range": range_, "period": period, "direction": direction,
                "speaker": "Priya Shah", "quote": source_text, "context_quotes": []},
        speaker_claimed="Priya Shah", speaker="Priya Shah", source=span(source_text),
        context=[span(text, "S27") for text in context_texts], origin="prepared",
    )


def result(*items, missed=()):
    return VerificationResult(
        items=list(items),
        possibly_missed=[MissedCandidate(segment_id="S4", speaker="Priya Shah", raw=raw, context="...")
                         for raw in missed],
        section_status={"prepared": "ok", "qa": "ok"},
    )


def key(figures=(), guidance=(), risks=(), must_not=()):
    return AnswerKey(figures=list(figures), guidance=list(guidance), risks=list(risks), must_not=list(must_not))


def gold_figure(anchor, value, period="Q2 2026", basis="not stated"):
    return {"anchor": anchor, "value": value, "period": period, "basis": basis}


def gold_guidance(anchor, range_, period="Q3 2026", direction="not stated", qualifier_anchor=None):
    return {"anchor": anchor, "range": range_, "period": period, "direction": direction,
            "qualifier_anchor": qualifier_anchor}
