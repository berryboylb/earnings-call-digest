"""Earnings Call Digest: runs every transcript in data/ through parse -> extract."""

import sys
from pathlib import Path

from config import DATA_DIR, OUTPUT_DIR, load_settings
from extraction.extractor import run_extraction
from parsing.parser import parse_file
from providers.base import Provider
from providers.nvidia import NvidiaProvider
from report import print_extraction, print_parse


def run(provider: Provider, data_dir: Path = DATA_DIR, output_dir: Path = OUTPUT_DIR) -> bool:
    """Process every transcript in data_dir. Returns False if any extraction failed."""
    all_ok = True
    for transcript in sorted(data_dir.glob("*.txt")):
        print(f"\n##### {transcript.name}", flush=True)

        parsed = parse_file(transcript)
        print_parse(parsed)

        extraction = run_extraction(parsed, provider)
        print_extraction(extraction)

        output_dir.mkdir(exist_ok=True)
        output = output_dir / f"{transcript.stem}.extraction.json"
        output.write_text(extraction.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nwrote {output}", flush=True)

        all_ok &= all(section.status != "failed" for section in extraction.sections)
    return all_ok


if __name__ == "__main__":
    ok = run(NvidiaProvider(load_settings()))
    sys.exit(0 if ok else 1)
