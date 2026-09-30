import pytest

from parsing import ParseError, parse_transcript, segment_text


def test_text_with_no_speakers_raises():
    with pytest.raises(ParseError):
        parse_transcript("Some Company Q1 Call\n\nJust prose with no speaker labels.\n\nMore prose.")


def test_single_speaker_raises():
    with pytest.raises(ParseError):
        parse_transcript("Operator: Hello.\nOperator: Still me.\nOperator: Goodbye.")


def test_truncated_transcript_warns_mid_sentence(kestrel_text):
    assert not any("mid-sentence" in w for w in parse_transcript(kestrel_text).warnings)
    truncated = kestrel_text.rstrip().removesuffix(" next quarter.")
    assert any("mid-sentence" in w for w in parse_transcript(truncated).warnings)


def test_normalises_crlf_and_nbsp(kestrel_text, by_speaker):
    text = kestrel_text.replace("\n", "\r\n").replace("Daniel Okafor\r\n", "Daniel\u00a0Okafor\r\n")
    result = parse_transcript(text)
    assert len(by_speaker(result, "Daniel Okafor")) == 3


def test_meridian_end_to_end(meridian):
    segs = meridian.segments
    assert meridian.roster_source == "participant_list"
    assert len(segs) == 29
    assert [s.section for s in segs].index("qa") == 5
    assert segs[5].id == "S6" and segs[5].speaker == "Operator"

    emma_qa = [s for s in segs if s.speaker == "Emma Chen" and s.section == "qa"]
    assert len(emma_qa) == 1 and emma_qa[0].role == "management"

    s15, s17 = segs[14], segs[16]
    assert (s15.id, s15.speaker) == ("S15", "Priya Shah")
    assert (s17.id, s17.speaker) == ("S17", "Priya Shah")
    assert "$480 million" in segment_text(s15)
    assert "$460 million" in segment_text(s17)
    assert "$460 million" not in segment_text(s15)
