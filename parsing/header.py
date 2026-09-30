"""Reads the call's title and date from the header: the lines before the call starts."""

from constants.parsing import CALL_TITLE, FULL_DATE


def header_lines(lines: list[str], header_end: int) -> list[str]:
    """The non-empty lines before header_end, stripped."""
    return [line.strip() for line in lines[:header_end] if line.strip()]


def read_call_title(header: list[str]) -> str | None:
    """The line that names the call ("Q2 2026 Earnings Conference Call"). If the line just
    above it is a company name ("Meridian Cloud Systems plc"), it goes in front.

    Lines in capitals are skipped: they are notices ("SYNTHETIC TEST FIXTURE - NOT A REAL
    COMPANY OR EARNINGS CALL") or section labels, not titles.
    """
    for i, line in enumerate(header):
        if line.isupper() or not CALL_TITLE.search(line):
            continue
        previous = header[i - 1] if i > 0 else ""
        if previous and not previous.isupper() and not FULL_DATE.search(previous):
            return f"{previous} · {line}"
        return line
    return None


def read_call_date(header: list[str]) -> str | None:
    """The first full date in the header, e.g. "July 29, 2026" from "Wednesday July 29, 2026"."""
    for line in header:
        date = FULL_DATE.search(line)
        if date:
            return date.group()
    return None
