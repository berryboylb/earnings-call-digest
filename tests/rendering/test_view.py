from rendering.view import build_view
from tests.rendering.conftest import GENERATED_AT, META


def table(view, title):
    [found] = [table for table in view.tables if table.title == title]
    return found


def test_unverified_items_only_appear_in_needs_review(result):
    view = build_view(result, META, GENERATED_AT)
    main_tables = view.tables[:4]
    shown = " ".join(cell for t in main_tables for row in t.rows for cell in row)
    assert "Recurring revenue" not in shown and "Services growth" not in shown

    review = table(view, "Needs review")
    assert [row[0] for row in review.rows] == ["F3", "F4"]
    assert review.rows[1][2] == "value mismatch: extracted 14%, transcript says 12%; second reason"


def test_src_shows_source_and_context_segments(result):
    figures = table(build_view(result, META, GENERATED_AT), "Headline figures")
    assert [row[-1] for row in figures.rows] == ["S4", "S17+S15"]


def test_title_trust_line_and_footer(result):
    view = build_view(result, META, GENERATED_AT)
    assert view.title == "Meridian · Q2 2026 earnings call"  # no ticker in the transcript header
    assert view.subtitle == "Call date August 6, 2026 · Source: fictional test transcript"
    assert view.trust_line == ("3 of 5 extracted items verified against the transcript · "
                               "2 need review · 1 numbers possibly missed")
    assert view.banner is None
    assert "replayed from cache" in view.footer and "abc123def456" in view.footer
    assert view.limits.startswith("Verified = quote, number and speaker match the transcript.")


def test_failed_qa_section_shows_banner_and_not_available(result):
    result.section_status["qa"] = "failed"
    result.items = [item for item in result.items if item.origin != "qa"]
    view = build_view(result, META, GENERATED_AT)
    assert view.banner == "INCOMPLETE: extraction failed for qa. Missing items may exist."
    qa = table(view, "Q&A: what analysts pushed on")
    assert qa.rows == [] and qa.empty_text == "Not available: extraction failed for this section."


def test_empty_sections_say_none_identified(result):
    view = build_view(result, META, GENERATED_AT)
    assert table(view, "Guidance").empty_text == "None identified."
