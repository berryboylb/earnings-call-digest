from schema.verification import VerifiedItem
from tests.verification.conftest import figure, make_run
from verification.dedupe import merge_duplicates
from verification.verifier import verify_run

CONFLICT = "conflicting values for the same metric and period"


def verified_figure(value, speaker="Jane Doe"):
    fields = figure("Revenue", value, "Q3 2026", speaker, f"Revenue was {value}.")
    return VerifiedItem(kind="figure", fields=fields, speaker_claimed=speaker, speaker=speaker, origin="prepared")


def test_verified_figures_with_different_values_are_both_unverified():
    items = merge_duplicates([verified_figure("$100 million"), verified_figure("$120 million")])
    assert len(items) == 2  # different values are never merged
    for item in items:
        assert item.status == "unverified"
        assert item.reasons[0].startswith(f"{CONFLICT} ($100 million vs $120 million)")


def test_same_value_written_differently_is_merged():
    items = merge_duplicates([verified_figure("$1.2 billion"), verified_figure("$1,200 million", speaker="John Roe")])
    assert len(items) == 1
    assert items[0].status == "verified" and items[0].notes == ["also stated by John Roe"]


def test_meridian_correction_is_flagged_as_a_conflict(meridian):
    corrected = figure("Platform backlog", "$460 million", "June 30, 2026", "Priya Shah",
                       "The correct platform backlog at June 30 is $460 million, not $480 million.",
                       context_quotes=["Platform backlog at June 30 was $480 million."])
    original = figure("Platform backlog", "$480 million", "June 30, 2026", "Priya Shah",
                      "Platform backlog at June 30 was $480 million.")
    result = verify_run(meridian, make_run(qa={"figures": [corrected, original]}))

    assert len(result.items) == 2
    for item in result.items:
        assert item.status == "unverified"
        assert f"{CONFLICT} ($460 million vs $480 million)" in item.reasons[0]
    assert [match.segment_id for match in result.items[0].context] == ["S15"]  # the $480M statement, as context
