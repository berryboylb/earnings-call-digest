from parsing import parse_transcript


def test_no_segments_created_from_roster_lines(parsed):
    assert [s.speaker for s in parsed.segments] == [
        "Operator", "Sofia Marquez", "Daniel Okafor", "Helen M. Ortiz",
        "Operator", "Ravi Menon", "Daniel Okafor",
        "Operator", "Claire Dubois", "Helen M. Ortiz",
        "Operator", "Daniel Okafor",
    ]
    all_text = " ".join(p.text for s in parsed.segments for p in s.paragraphs)
    for roster_line in ["Company Participants", "Sofia Marquez - Head of Investor Relations",
                        "Conference Call Participants", "Ravi Menon - Bank of Examples"]:
        assert roster_line not in all_text


def test_list_under_unrecognised_header_warns_and_falls_back_to_heuristic(layout_b):
    roster_block = (
        "\n\nSpeakers\n\n"
        "Tom Reyes - Chief Executive Officer\n"
        "Ana Lopez - Chief Financial Officer\n"
        "Raj Patel - Barclays\n"
        "\n\nOperator:"
    )
    text = layout_b.replace("\n\nOperator:", roster_block, 1)
    result = parse_transcript(text)

    assert result.roster_source == "heuristic"
    assert result.participants == []
    assert (
        "Possible participant list under unrecognised header 'Speakers'; "
        "roles not assigned from it"
    ) in result.warnings
    # Roles come from the heuristic, and the list lines don't become speaker turns
    # (not even empty ones that are dropped later).
    assert result.segments[0].speaker == "Operator"
    assert not any("Dropped speaker lines" in w for w in result.warnings)
    assert {s.speaker: s.role for s in result.segments} == {
        "Operator": "operator",
        "Tom Reyes": "management",
        "Ana Lopez": "management",
        "Raj Patel": "analyst",
        "Kim Wu": "analyst",
        "Mark Stone": "unknown",
    }
    assert "Chief Executive Officer" not in " ".join(p.text for s in result.segments for p in s.paragraphs)


def test_no_unrecognised_header_warning_for_recognised_or_absent_list(parsed, layout_b):
    assert not any("unrecognised header" in w for w in parsed.warnings)
    assert not any("unrecognised header" in w for w in parse_transcript(layout_b).warnings)
