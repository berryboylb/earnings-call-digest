"""The shape of the one-page digest. Every output format is drawn from a DigestView,
so the HTML, PDF and DOCX can never disagree."""

from dataclasses import dataclass


@dataclass
class DigestMeta:
    """Facts about the call and the run, shown in the title and footer."""

    call_title: str  # from the transcript's header, or the file name if it has none
    call_date: str
    source: str  # the transcript's file name
    model: str
    prompt_version: str
    structured_output_mode: str | None
    replayed: bool  # True if every LLM answer came from the cache
    transcript_sha256: str  # first 12 characters


@dataclass
class Table:
    title: str
    headers: list[str]
    rows: list[list[str]]
    empty_text: str  # shown instead of the table when it has no rows
    note: str | None = None


@dataclass
class DigestView:
    title: str
    subtitle: str
    banner: str | None  # set when an extraction section failed
    trust_line: str
    tables: list[Table]
    footer: str
    limits: str
