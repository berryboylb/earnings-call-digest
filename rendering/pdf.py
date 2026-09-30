"""Prints the digest's HTML to an A4 PDF with WeasyPrint."""

from pathlib import Path

from constants.rendering import PDF_UNAVAILABLE


class PdfUnavailable(Exception):
    """WeasyPrint can't run here (usually its system libraries aren't installed)."""


def write_pdf(html: str, path: Path) -> None:
    """Write the PDF. Raises PdfUnavailable, with a clear message, if WeasyPrint can't load."""
    try:
        # Imported here, so a missing system library only affects the PDF.
        from weasyprint import HTML
    except (ImportError, OSError) as error:
        raise PdfUnavailable(PDF_UNAVAILABLE.format(error=_first_line(error))) from error
    HTML(string=html).write_pdf(path)


def _first_line(error: Exception) -> str:
    """The short part of the error: "cannot load library 'libgobject-2.0-0'", without the search details."""
    text = str(error).strip()
    if not text:
        return type(error).__name__
    return text.splitlines()[0].split(": ")[0]
