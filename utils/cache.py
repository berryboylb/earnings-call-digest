"""Disk cache for LLM responses, so repeated runs are free and reproducible."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

CacheMode = Literal["auto", "cached", "refresh"]


def cache_key(
    *,
    base_url: str,
    model: str,
    reasoning_effort: str,
    prompt_version: str,
    name: str,
    system: str,
    user: str,
    schema: dict,
) -> str:
    """A fingerprint of everything that can change the answer.

    The same request always gets the same key, so a repeat run reuses the saved answer.
    base_url is part of it, so one provider's answer is never replayed as another's.
    """
    payload = [base_url, model, reasoning_effort, prompt_version, name, system, user, schema]
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class DiskCache:
    """One JSON file per key: raw content, parsed JSON, timestamp and how it was produced."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def _file_for(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> dict | None:
        """The saved entry for this key, or None if there isn't one."""
        file = self._file_for(key)
        if not file.exists():
            return None
        return json.loads(file.read_text(encoding="utf-8"))

    def put(self, key: str, *, raw: str, parsed: dict, structured_output_mode: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        entry = {
            "raw": raw,
            "parsed": parsed,
            "structured_output_mode": structured_output_mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._file_for(key).write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
