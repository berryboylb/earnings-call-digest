from parsing import parse_file, parse_transcript, segment_text


def test_sentence_starting_with_name_is_not_a_speaker_line(parsed, by_speaker):
    ceo_prepared = by_speaker(parsed, "Daniel Okafor")[0]
    texts = [p.text for p in ceo_prepared.paragraphs]
    assert any(t.endswith("Helen Ortiz and her team closed the books two days earlier than last year.") for t in texts)
    assert any(t.startswith("Helen Ortiz, our Chief Financial Officer, will now walk") for t in texts)
    assert len(by_speaker(parsed, "Helen M. Ortiz")) == 2


def test_rejected_speaker_like_line_is_merged_with_warning(kestrel_path, kestrel_text, by_speaker):
    # "Grace Lin" is not in the participant list, appears once, and nobody introduces her.
    anchor = "We have not seen cancellations.\n"
    text = kestrel_text.replace(anchor, anchor + "\nGrace Lin\n\nRenewal rates are on track.\n")
    line_no = text.split("\n").index("Grace Lin") + 1
    result = parse_transcript(text)

    cfo_answer = by_speaker(result, "Helen M. Ortiz")[1]
    assert "Grace Lin" in segment_text(cfo_answer)
    assert "Renewal rates are on track." in segment_text(cfo_answer)
    assert "Grace Lin" not in {s.speaker for s in result.segments}
    assert (
        f"Possible speaker line not recognised: 'Grace Lin' (line {line_no}), "
        "text attributed to Helen M. Ortiz"
    ) in result.warnings
    assert not any("Possible speaker line" in w for w in parse_file(kestrel_path).warnings)
