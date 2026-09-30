import pytest
from docx import Document

from rendering.docx import write_docx
from rendering.html import render_html
from rendering.view import build_view
from tests.rendering.conftest import GENERATED_AT, META


def test_html_escapes_text_from_the_transcript_or_model(result):
    result.items[0].fields["metric"] = "<script>alert(1)</script>"
    html = render_html(build_view(result, META, GENERATED_AT))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_html_shows_every_table_and_the_limits_line(result):
    view = build_view(result, META, GENERATED_AT)
    html = render_html(view)
    for t in view.tables:
        assert t.title.replace("&", "&amp;") in html
    assert view.limits in html


def test_docx_has_the_same_rows_per_table_as_the_view(result, tmp_path):
    view = build_view(result, META, GENERATED_AT)
    path = tmp_path / "digest.docx"
    write_docx(view, path)

    word_tables = Document(path).tables
    view_tables_with_rows = [t for t in view.tables if t.rows]
    assert len(word_tables) == len(view_tables_with_rows)
    for word_table, view_table in zip(word_tables, view_tables_with_rows):
        assert len(word_table.rows) == len(view_table.rows) + 1  # plus the header row


def test_pdf_is_written(result, tmp_path):
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        pytest.skip("WeasyPrint's system libraries aren't installed (macOS: brew install pango)")
    from rendering.pdf import write_pdf

    path = tmp_path / "digest.pdf"
    write_pdf(render_html(build_view(result, META, GENERATED_AT)), path)
    assert path.read_bytes().startswith(b"%PDF")


def test_missing_weasyprint_gives_a_clear_error_not_a_crash(result, tmp_path, monkeypatch):
    import builtins

    from rendering.pdf import PdfUnavailable, write_pdf
    real_import = builtins.__import__

    def no_weasyprint(name, *args, **kwargs):
        if name == "weasyprint":
            raise OSError("cannot load library 'libgobject-2.0-0'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_weasyprint)
    with pytest.raises(PdfUnavailable, match="brew install pango"):
        write_pdf("<p>x</p>", tmp_path / "digest.pdf")
