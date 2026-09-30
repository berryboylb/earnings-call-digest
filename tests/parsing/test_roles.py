from parsing import parse_transcript, segment_text


def test_roles_come_from_participant_list(parsed):
    assert parsed.roster_source == "participant_list"
    roles = {s.speaker: s.role for s in parsed.segments}
    assert roles == {
        "Operator": "operator",
        "Sofia Marquez": "management",
        "Daniel Okafor": "management",
        "Helen M. Ortiz": "management",  # speaker lines say "Helen Ortiz": middle initial tolerated
        "Ravi Menon": "analyst",
        "Claire Dubois": "analyst",
    }
    assert parsed.unknown_speakers == []


def test_layout_b_without_participant_list_infers_roles(layout_b):
    result = parse_transcript(layout_b)
    assert result.roster_source == "heuristic"
    roles = {s.speaker: s.role for s in result.segments}
    assert roles == {
        "Operator": "operator",
        "Tom Reyes": "management",
        "Ana Lopez": "management",
        "Raj Patel": "analyst",
        "Kim Wu": "analyst",
        "Mark Stone": "unknown",  # speaks only in Q&A and is never introduced
    }
    assert result.unknown_speakers == ["Mark Stone"]
    assert [s.section for s in result.segments] == ["prepared"] * 3 + ["qa"] * 7
    assert "Tom Reyes: that label" in segment_text(result.segments[2])
    assert any("No participant list" in w for w in result.warnings)
    assert any("Mark Stone" in w for w in result.warnings)


def test_unidentified_analyst_is_unknown_with_warning(kestrel_text):
    text = kestrel_text.replace("Claire Dubois\n\nCan you", "Unidentified Analyst\n\nCan you")
    result = parse_transcript(text)
    roles = {s.speaker: s.role for s in result.segments}
    assert roles["Unidentified Analyst"] == "unknown"
    assert result.unknown_speakers == ["Unidentified Analyst"]
    assert "Could not determine role for: Unidentified Analyst" in result.warnings
