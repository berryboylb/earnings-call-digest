from parsing import segment_text


def test_safe_harbor_flagged_as_boilerplate(parsed, by_speaker):
    ir = by_speaker(parsed, "Sofia Marquez")[0]
    assert [p.boilerplate for p in ir.paragraphs] == [False, True, False]
    assert "forward-looking" in ir.paragraphs[1].text
    assert "forward-looking" not in segment_text(ir)
    assert "forward-looking" in segment_text(ir, include_boilerplate=True)
    others = [p for s in parsed.segments if s is not ir for p in s.paragraphs]
    assert not any(p.boilerplate for p in others)
