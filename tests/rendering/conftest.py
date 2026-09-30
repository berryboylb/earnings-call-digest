"""VerificationResult objects built by hand for the rendering tests."""

from datetime import datetime, timezone

import pytest

from schema.digest import DigestMeta
from schema.verification import (
    MissedCandidate,
    SourceMatch,
    VerificationResult,
    VerifiedItem,
)

GENERATED_AT = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)

META = DigestMeta(
    call_title="Meridian Cloud Systems plc · Q2 2026 Earnings Conference Call",
    call_date="August 6, 2026", source="meridian.txt", model="test/model", prompt_version="v1",
    structured_output_mode="json_schema", replayed=True, transcript_sha256="abc123def456",
)


def match(segment_id):
    if segment_id is None:
        return None
    return SourceMatch(segment_id=segment_id, paragraph_index=0, start=0, end=10, text="...",
                       method="exact", score=1.0, in_boilerplate=False)


def figure_item(item_id, metric, value, status="verified", reasons=(), source="S4", context=()):
    fields = {"metric": metric, "value": value, "period": "Q2 2026", "basis": "not stated",
              "is_comparison": False, "speaker": "Priya Shah", "quote": "...", "context_quotes": []}
    return VerifiedItem(id=item_id, kind="figure", status=status, reasons=list(reasons), fields=fields,
                        speaker_claimed="Priya Shah", speaker="Priya Shah", source=match(source),
                        context=[match(segment_id) for segment_id in context], origin="prepared")


def qa_item(item_id, topic):
    fields = {"topic": topic, "asked_by": "Alex Morgan", "answer_quality": "direct",
              "speaker": "Daniel Okafor", "quote": "..."}
    return VerifiedItem(id=item_id, kind="qa", fields=fields, speaker_claimed="Daniel Okafor",
                        speaker="Daniel Okafor", source=match("S8"), origin="qa")


@pytest.fixture
def result():
    return VerificationResult(
        items=[
            figure_item("F1", "Revenue", "$850 million"),
            figure_item("F2", "Platform backlog", "$460 million", source="S17", context=["S15"]),
            figure_item("F3", "Recurring revenue", "$150 million", status="unverified",
                        reasons=["quote not found in transcript"], source=None),
            figure_item("F4", "Services growth", "14%", status="unverified",
                        reasons=["value mismatch: extracted 14%, transcript says 12%", "second reason"]),
            qa_item("Q1", "2027 revenue growth assumption"),
        ],
        possibly_missed=[MissedCandidate(segment_id="S3", speaker="Daniel Okafor", raw="$5 billion",
                                         context="We aim to reach $5 billion in annual revenue")],
        section_status={"prepared": "ok", "qa": "ok"},
    )
