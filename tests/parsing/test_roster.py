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

