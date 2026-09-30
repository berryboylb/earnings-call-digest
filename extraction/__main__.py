"""CLI: extract structured items from a transcript and write out/<stem>.extraction.json.

Usage:
    uv run python -m extraction data/<file>.txt [--cached | --refresh | --fixture PATH]

Exit codes: 0 all sections ok or empty, 1 bad input or settings, 2 a section failed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from parsing import ParseError, parse_file

from .client import FixtureProvider, NvidiaProvider
from .config import ConfigError, load_settings
from .extract import run_extraction
from .models import Extraction, ExtractionRun

OUT_DIR = Path("out")


def _item_lines(extraction: Extraction) -> list[str]:
    """kind | metric/theme/topic | value/range | period | speaker | first 80 chars of quote"""
    rows = (
        [("figure", f.metric, f.value, f.period, f.speaker, f.quote) for f in extraction.figures]
        + [("guidance", g.metric, g.range, g.period, g.speaker, g.quote) for g in extraction.guidance]
        + [("risk", r.theme, r.hedging_phrase, "-", r.speaker, r.quote) for r in extraction.risks]
        + [("qa_topic", q.topic, f"asked by {q.asked_by}, {q.answer_quality}", "-", q.speaker, q.quote)
           for q in extraction.qa_topics]
    )
    return [" | ".join([*row[:5], row[5][:80]]) for row in rows]


def _print_run(run: ExtractionRun) -> None:
    u = run.usage
    print(f"model: {run.model} | prompt {run.prompt_version} | structured output: {run.structured_output_mode}")
    print(f"usage: {u.calls} calls, {u.replayed_calls} replayed, "
          f"{u.prompt_tokens} prompt + {u.completion_tokens} completion tokens")
    for s in run.sections:
        source = "replayed" if s.replayed else "live"
        if s.extraction is None:
            detail = f"error: {s.error}" if s.error else "no input"
            print(f"\n[{s.name}] {s.status} | {detail}")
            continue
        e = s.extraction
        print(f"\n[{s.name}] {s.status} | {source} | figures {len(e.figures)}, guidance {len(e.guidance)}, "
              f"risks {len(e.risks)}, qa_topics {len(e.qa_topics)}")
        for line in _item_lines(e):
            print(f"  {line}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m extraction")
    parser.add_argument("transcript")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cached", action="store_true", help="replay from the cache only; never call the API")
    mode.add_argument("--refresh", action="store_true", help="always call the API and overwrite the cache")
    mode.add_argument("--fixture", metavar="PATH", help="replay outputs from a fixture JSON file")
    args = parser.parse_args(argv)

    try:
        parsed = parse_file(args.transcript)
        if args.fixture:
            provider = FixtureProvider(args.fixture)
        else:
            cache_mode = "cached" if args.cached else "refresh" if args.refresh else "auto"
            provider = NvidiaProvider(load_settings(require_api_key=not args.cached), cache_mode=cache_mode)
    except (OSError, ParseError, ConfigError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    run = run_extraction(parsed, provider)
    _print_run(run)

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / f"{Path(args.transcript).stem}.extraction.json"
    out_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nwrote {out_path}")
    return 2 if any(s.status == "failed" for s in run.sections) else 0


if __name__ == "__main__":
    sys.exit(main())
