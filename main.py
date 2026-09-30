"""Earnings Call Digest: runs every transcript in data/ through parse -> extract -> verify -> render.

Each transcript gets a folder out/<name>/ with extraction.json, verified.json and the
digest as HTML, PDF and DOCX. Call details (company, ticker, quarter, date, source)
come from data/<name>.json.
"""

import sys
from pathlib import Path

from config import DATA_DIR, OUTPUT_DIR, load_settings
from constants.rendering import DIGEST_FILES
from extraction.extractor import run_extraction
from parsing.parser import parse_file
from providers.base import Provider
from providers.nvidia import NvidiaProvider
from rendering.docx import write_docx
from rendering.html import render_html
from rendering.meta import load_meta
from rendering.pdf import PdfUnavailable, write_pdf
from rendering.view import build_view
from report import print_extraction, print_parse, print_verification
from verification.verifier import verify_run


def run(provider: Provider, data_dir: Path = DATA_DIR, output_dir: Path = OUTPUT_DIR) -> bool:
    """Process every transcript in data_dir. Returns False if any extraction failed."""
    all_ok = True
    for transcript in sorted(data_dir.glob("*.txt")):
        print(f"\n##### {transcript.name}", flush=True)
        folder = output_dir / transcript.stem
        folder.mkdir(parents=True, exist_ok=True)

        print("\n=== 1. parse ===")
        parsed = parse_file(transcript)
        print_parse(parsed)

        print("\n=== 2. extract ===", flush=True)
        extraction = run_extraction(parsed, provider)
        print_extraction(extraction)
        _save(folder / "extraction.json", extraction.model_dump_json(indent=2))

        print("\n=== 3. verify ===")
        verification = verify_run(parsed, extraction)
        print_verification(verification)
        _save(folder / "verified.json", verification.model_dump_json(indent=2))

        print("\n=== 4. render ===")
        view = build_view(verification, load_meta(transcript, extraction))
        html = render_html(view)
        _save(folder / DIGEST_FILES["html"], html)
        try:
            write_pdf(html, folder / DIGEST_FILES["pdf"])
            print(f"wrote {folder / DIGEST_FILES['pdf']}")
        except PdfUnavailable as error:
            print(error)
        write_docx(view, folder / DIGEST_FILES["docx"])
        print(f"wrote {folder / DIGEST_FILES['docx']}")
        print(view.trust_line, flush=True)

        all_ok &= all(section.status != "failed" for section in extraction.sections)
    return all_ok


def _save(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path}")


if __name__ == "__main__":
    ok = run(NvidiaProvider(load_settings()))
    sys.exit(0 if ok else 1)
