"""Transcripts in the style many real calls use: "NAME, Firm: text" labels, capital-letter
names, one paragraph per line and almost no blank lines. The text below is made up."""

from parsing.parser import parse_transcript

REAL_STYLE = """\
Acme Corp FY26 Fourth Quarter Earnings Conference Call
Jane Doe, John Roe
JANE DOE:
Good afternoon and thank you for joining us. With me is John Roe, chief executive officer.
During this call, we will be making forward-looking statements. These statements are subject to risks and uncertainties, and actual results could differ materially.
And with that, I will turn the call over to John.
JOHN ROE:
Thank you, Jane.
Revenue was $12 billion, up 15%.
Operating margin was 41%, up 2 points.

With that, let's go to Q&A, Jane.
JANE DOE: Thanks, John. We will now move over to Q&A. Operator, please go ahead.
OPERATOR: Our first question comes from the line of Karl Smith with UBS. Please proceed.
KARL SMITH, UBS: Thanks. John, how durable is the 15% growth?
And how should we think about margins next year?
JOHN ROE: Thank you, Karl. We see demand continuing to exceed supply.
KARL SMITH: Very helpful, thanks.
JANE DOE: Thanks, Karl. Operator, next question, please.
OPERATOR: The next question comes from the line of Ana Lee with Jefferies. Please proceed.
ANA LEE, Jefferies: Thanks. John, what about pricing?
JOHN ROE: Pricing is stable.
"""


def speakers_and_roles(result):
    return [(segment.speaker, segment.role) for segment in result.segments]


def test_name_firm_colon_labels_are_speaker_turns():
    result = parse_transcript(REAL_STYLE)
    turns = speakers_and_roles(result)
    assert ("KARL SMITH", "analyst") in turns and ("ANA LEE", "analyst") in turns
    operator_text = " ".join(p.text for s in result.segments if s.speaker == "Operator" for p in s.paragraphs)
    assert "how durable" not in operator_text  # the question is not credited to the Operator
    assert result.unknown_speakers == []
    assert not any("not recognised" in warning for warning in result.warnings)


def test_follow_up_by_the_same_analyst_is_recognised():
    result = parse_transcript(REAL_STYLE)
    karl_turns = [segment for segment in result.segments if segment.speaker == "KARL SMITH"]
    assert len(karl_turns) == 2
    assert karl_turns[1].paragraphs[0].text == "Very helpful, thanks."


def test_unrecognised_name_firm_label_is_warned_about_not_silently_merged():
    # Nobody introduces BOB KING and he speaks once, so there's no evidence he's a speaker.
    text = REAL_STYLE.replace("JOHN ROE: Pricing is stable.", "JOHN ROE: Pricing is stable.\nBOB KING, Citi: One more?")
    warnings = parse_transcript(text).warnings
    assert any("Possible speaker line not recognised: 'BOB KING, Citi: One more?'" in warning for warning in warnings)


def test_one_paragraph_per_line_when_blank_lines_are_rare():
    result = parse_transcript(REAL_STYLE)
    [ceo_prepared] = [s for s in result.segments if s.speaker == "JOHN ROE" and s.section == "prepared"]
    # the stray blank line doesn't switch the transcript back to blank-line paragraphs
    assert [p.text for p in ceo_prepared.paragraphs] == [
        "Thank you, Jane.",
        "Revenue was $12 billion, up 15%.",
        "Operating margin was 41%, up 2 points.",
        "With that, let's go to Q&A, Jane.",
    ]
    [ir_opening] = [s for s in result.segments if s.speaker == "JANE DOE"][:1]
    assert [p.boilerplate for p in ir_opening.paragraphs] == [False, True, False]  # only the safe-harbor line


def test_lines_wrapped_mid_sentence_are_joined():
    [question] = [s for s in parse_transcript(REAL_STYLE).segments if s.speaker == "KARL SMITH"][:1]
    wrapped = REAL_STYLE.replace("how durable is the 15% growth?", "how durable is\nthe 15% growth?")
    [wrapped_question] = [s for s in parse_transcript(wrapped).segments if s.speaker == "KARL SMITH"][:1]
    assert wrapped_question.paragraphs[0].text == question.paragraphs[0].text


def test_text_after_a_name_firm_label_is_kept():
    # "Jefferies: Thanks. John, what about pricing?" must not be mistaken for a job title.
    [ana] = [segment for segment in parse_transcript(REAL_STYLE).segments if segment.speaker == "ANA LEE"]
    assert ana.paragraphs[0].text == "Thanks. John, what about pricing?"


def test_header_line_listing_the_speakers_is_not_a_speaker():
    result = parse_transcript(REAL_STYLE)
    assert result.segments[0].speaker == "JANE DOE"  # not "Jane Doe" from the "Jane Doe, John Roe" line
    assert result.segments[0].paragraphs[0].text.startswith("Good afternoon")
    assert not any("Dropped speaker lines" in warning for warning in result.warnings)
