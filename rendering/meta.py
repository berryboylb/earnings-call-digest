"""Collects the facts shown in the digest's title and footer."""

import hashlib
import json
from pathlib import Path

from schema.digest import DigestMeta
from schema.extraction import ExtractionRun


def load_meta(transcript: Path, extraction: ExtractionRun) -> DigestMeta:
    """Call details come from a file next to the transcript (data/meridian.json for
    data/meridian.txt); run details come from the extraction run."""
    call = _call_details(transcript)
    usage = extraction.usage
    return DigestMeta(
        company=call.get("company", transcript.stem),
        ticker=call.get("ticker", ""),
        quarter=call.get("quarter", "unknown quarter"),
        call_date=call.get("call_date", "unknown"),
        source=call.get("source", "unknown"),
        model=extraction.model,
        prompt_version=extraction.prompt_version,
        structured_output_mode=extraction.structured_output_mode,
        replayed=usage.calls == 0 and usage.replayed_calls > 0,
        transcript_sha256=hashlib.sha256(transcript.read_bytes()).hexdigest()[:12],
    )


def _call_details(transcript: Path) -> dict:
    details_file = transcript.with_suffix(".json")
    if not details_file.exists():
        return {}
    return json.loads(details_file.read_text(encoding="utf-8"))
