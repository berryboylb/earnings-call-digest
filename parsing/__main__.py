"""CLI: print a parsed transcript's segments and warnings.

Usage:
    uv run python -m parsing data/<file>.txt
"""

from __future__ import annotations

import sys

from .models import ParseError
from .parser import parse_file


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m parsing <transcript.txt>", file=sys.stderr)
        return 2
    try:
        result = parse_file(args[0])
    except (OSError, ParseError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"roster_source: {result.roster_source}")
    width = max(len(s.speaker) for s in result.segments)
    for s in result.segments:
        # "." no boilerplate, "B" all boilerplate, "b" partly boilerplate
        markers = "".join(
            "B" if p.boilerplate else "b" if p.boilerplate_spans else "." for p in s.paragraphs
        )
        print(f"{s.id:<4} {s.speaker:<{width}}  {s.role:<10}  {s.section:<8}  {markers}")
    print(f"warnings ({len(result.warnings)}):")
    for w in result.warnings:
        print(f"  - {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
