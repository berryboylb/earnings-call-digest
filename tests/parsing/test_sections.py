from parsing import segment_text


def test_qa_starts_at_operator_handoff(parsed):
    sections = [s.section for s in parsed.segments]
    first_qa = sections.index("qa")
    handoff = parsed.segments[first_qa]
    assert handoff.speaker == "Operator"
    assert "first question" in segment_text(handoff)
    assert all(sec == "prepared" for sec in sections[:first_qa])
    assert all(sec == "qa" for sec in sections[first_qa:])
    analysts = [s for s in parsed.segments if s.role == "analyst"]
    assert len(analysts) == 2 and all(s.section == "qa" for s in analysts)
