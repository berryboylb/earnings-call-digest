"""Renders the digest as a Word document, from the same DigestView as the HTML."""

from pathlib import Path

from docx import Document
from docx.shared import Pt

from schema.digest import DigestView

SMALL_TEXT = Pt(8)


def write_docx(view: DigestView, path: Path) -> None:
    document = Document()
    document.add_heading(view.title, level=1)
    document.add_paragraph(view.subtitle)
    if view.banner:
        document.add_paragraph().add_run(view.banner).bold = True
    document.add_paragraph(view.trust_line)

    for table in view.tables:
        document.add_heading(table.title, level=2)
        if table.note:
            document.add_paragraph().add_run(table.note).italic = True
        if not table.rows:
            document.add_paragraph(table.empty_text)
            continue

        word_table = document.add_table(rows=1, cols=len(table.headers))
        word_table.style = "Table Grid"
        for cell, header in zip(word_table.rows[0].cells, table.headers):
            cell.text = ""
            cell.paragraphs[0].add_run(header).bold = True
        for row in table.rows:
            cells = word_table.add_row().cells
            for cell, value in zip(cells, row):
                cell.text = value

    for text in [view.footer, view.limits]:
        document.add_paragraph().add_run(text).font.size = SMALL_TEXT

    document.save(path)
