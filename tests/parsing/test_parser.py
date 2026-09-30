import pytest

from parsing import ParseError, parse_transcript


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
