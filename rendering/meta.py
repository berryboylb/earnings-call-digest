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
        answered_by=answered_by(extraction),
        prompt_version=extraction.prompt_version,
        structured_output_mode=extraction.structured_output_mode,
        replayed=usage.calls == 0 and usage.replayed_calls > 0,
        transcript_sha256=hashlib.sha256(transcript.read_bytes()).hexdigest()[:12],
    )


def answered_by(extraction: ExtractionRun) -> str:
    """Which model actually answered each section, never just the configured one.

    e.g. "prepared: nvidia/nemotron-3-super-120b-a12b (4 calls);
          qa: openai/gpt-oss-20b (fallback after nvidia/nemotron-3-super-120b-a12b: timed out after 600s)"
    """
    parts = []
    for section in extraction.sections:
        if section.status == "empty_input":
            continue
        answered = [call for call in section.calls if call.status == "ok"]
        if not answered:
            parts.append(f"{section.name}: no answer ({section.error})")
            continue
        models = []
        for call in answered:
            if call.model not in models:
                models.append(call.model)
        descriptions = []
        for model in models:
            calls = [call for call in answered if call.model == model]
            count = f"{len(calls)} call" + ("" if len(calls) == 1 else "s")
            earlier = [failure for call in calls for failure in call.earlier_failures]
            fallback = f", fallback after {'; '.join(earlier)}" if earlier else ""
            descriptions.append(f"{model} ({count}{fallback})")
        failed = len(section.calls) - len(answered)
        if failed:
            descriptions.append(f"{failed} call{'' if failed == 1 else 's'} failed")
        parts.append(f"{section.name}: {', '.join(descriptions)}")
    return "; ".join(parts) or "no calls"
