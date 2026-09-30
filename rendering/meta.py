"""Collects the facts shown in the digest's title and footer."""

import hashlib
from pathlib import Path

from schema.digest import DigestMeta
from schema.extraction import ExtractionRun
from schema.transcript import ParsedTranscript


def load_meta(transcript: Path, parsed: ParsedTranscript, extraction: ExtractionRun) -> DigestMeta:
    """The call's title and date come from the transcript's own header; the run details
    come from the extraction run."""
    usage = extraction.usage
    return DigestMeta(
        call_title=parsed.call_title or transcript.stem,
        call_date=parsed.call_date or "unknown",
        source=transcript.name,
        model=extraction.model,
        prompt_version=extraction.prompt_version,
        structured_output_mode=extraction.structured_output_mode,
        replayed=usage.calls == 0 and usage.replayed_calls > 0,
        transcript_sha256=hashlib.sha256(transcript.read_bytes()).hexdigest()[:12],
    )
