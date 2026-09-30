from pathlib import Path

import pytest

from parse import ParseError, parse_file, parse_transcript, segment_text

FIXTURE = Path(__file__).parent / "fixtures" / "fictional_kestrel_q2.txt"

# Fictional Layout B transcript: inline "Name: text" and no participant list.
LAYOUT_B = """\
Acme Widgets Q1 2026 Earnings Call (fictional)

Operator: Good morning. I will now turn the call over to Tom Reyes, our CEO.
Tom Reyes: Thank you. Revenue was $10.0 million, up 5%.
Ana Lopez: Thanks, Tom. Gross margin was 30%. Tom Reyes: that label inside a sentence is not a speaker.
Operator: We will now open the line for questions. Our first question comes from Raj Patel with Barclays.
Raj Patel: How should we think about margins next year?
Ana Lopez: We expect them to be stable.
Mark Stone: I would add that pricing is holding up.
Operator: Our next question comes from Kim Wu with UBS.
Kim Wu: What about hiring?
Mark Stone: Hiring is flat.
"""


@pytest.fixture(scope="module")
def parsed():
    return parse_file(FIXTURE)


def by_speaker(result, name):
    return [s for s in result.segments if s.speaker == name]


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


def test_safe_harbor_flagged_as_boilerplate(parsed):
    ir = by_speaker(parsed, "Sofia Marquez")[0]
    assert [p.boilerplate for p in ir.paragraphs] == [False, True, False]
    assert "forward-looking" in ir.paragraphs[1].text
    assert "forward-looking" not in segment_text(ir)
    assert "forward-looking" in segment_text(ir, include_boilerplate=True)
    others = [p for s in parsed.segments if s is not ir for p in s.paragraphs]
    assert not any(p.boilerplate for p in others)


def test_sentence_starting_with_name_is_not_a_speaker_line(parsed):
    ceo_prepared = by_speaker(parsed, "Daniel Okafor")[0]
    texts = [p.text for p in ceo_prepared.paragraphs]
    assert any(t.endswith("Helen Ortiz and her team closed the books two days earlier than last year.") for t in texts)
    assert any(t.startswith("Helen Ortiz, our Chief Financial Officer, will now walk") for t in texts)
    assert len(by_speaker(parsed, "Helen M. Ortiz")) == 2


def test_layout_b_without_participant_list_infers_roles():
    result = parse_transcript(LAYOUT_B)
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


def test_text_with_no_speakers_raises():
    with pytest.raises(ParseError):
        parse_transcript("Some Company Q1 Call\n\nJust prose with no speaker labels.\n\nMore prose.")


def test_single_speaker_raises():
    with pytest.raises(ParseError):
        parse_transcript("Operator: Hello.\nOperator: Still me.\nOperator: Goodbye.")


def test_truncated_transcript_warns_mid_sentence():
    full = FIXTURE.read_text()
    assert not any("mid-sentence" in w for w in parse_transcript(full).warnings)
    truncated = full.rstrip().removesuffix(" next quarter.")
    assert any("mid-sentence" in w for w in parse_transcript(truncated).warnings)


def test_normalises_crlf_and_nbsp():
    text = FIXTURE.read_text().replace("\n", "\r\n").replace("Daniel Okafor\r\n", "Daniel Okafor\r\n")
    result = parse_transcript(text)
    assert len(by_speaker(result, "Daniel Okafor")) == 3


def test_rejected_speaker_like_line_is_merged_with_warning():
    # "Grace Lin" is not in the participant list, appears once, and nobody introduces her.
    anchor = "We have not seen cancellations.\n"
    text = FIXTURE.read_text().replace(anchor, anchor + "\nGrace Lin\n\nRenewal rates are on track.\n")
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
    assert not any("Possible speaker line" in w for w in parse_file(FIXTURE).warnings)
