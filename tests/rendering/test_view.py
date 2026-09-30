from rendering.view import build_view
from schema.verification import MissedCandidate, VerifiedItem
from tests.rendering.conftest import GENERATED_AT, META, figure_item, match


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
    assert view.title == "Meridian Cloud Systems plc · Q2 2026 Earnings Conference Call"
    assert view.subtitle == "Call date August 6, 2026 · Source: meridian.txt"
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


def test_headline_figures_are_capped_by_priority_and_the_rest_listed_after_qa(result):
    minor = [figure_item(f"F{n}", f"Minor metric {n}", "$1 million") for n in range(10, 25)]
    result.items = [*minor, figure_item("F1", "Revenue", "$850 million"), figure_item("F2", "Free cash flow", "$135 million")]
    view = build_view(result, META, GENERATED_AT)
    headline = table(view, "Headline figures")
    assert len(headline.rows) == 12
    assert {"Revenue", "Free cash flow"} <= {row[0] for row in headline.rows}  # priority metrics always make it
    others = table(view, "Other reported figures")
    assert len(others.rows) == 5
    titles = [t.title for t in view.tables]
    assert titles.index("Q&A: what analysts pushed on") < titles.index("Other reported figures")


def test_risks_are_capped_at_six(result):
    result.items = [VerifiedItem(id=f"R{n}", kind="risk", speaker_claimed="A", speaker="A", source=match("S4"),
                                 origin="prepared", fields={"theme": f"Risk {n}", "hedging_phrase": "could",
                                                            "speaker": "A", "quote": "..."}) for n in range(1, 9)]
    view = build_view(result, META, GENERATED_AT)
    assert len(table(view, "Risks & hedging").rows) == 6
    assert [row[0] for row in table(view, "Other risk language").rows] == ["Risk 7", "Risk 8"]


def test_possibly_missed_is_capped_at_ten_with_currency_first(result):
    percents = [MissedCandidate(segment_id="S1", speaker="A", raw=f"{n}%", context="...") for n in range(1, 11)]
    dollars = [MissedCandidate(segment_id="S2", speaker="A", raw=f"${n} million", context="...") for n in range(1, 4)]
    result.possibly_missed = percents + dollars
    view = build_view(result, META, GENERATED_AT)
    [missed] = [t for t in view.tables if t.title.startswith("Possibly missed")]
    assert missed.title == "Possibly missed (showing 10 of 13)"
    assert [row[2] for row in missed.rows[:3]] == ["$1 million", "$2 million", "$3 million"]
    assert len(missed.rows) == 10
