import pytest

from constants.parsing import END_MARKER
from parsing.paragraphs import segment_text
from parsing.parser import parse_file, parse_transcript


def test_sentence_starting_with_name_is_not_a_speaker_line(parsed, by_speaker):
    ceo_prepared = by_speaker(parsed, "Daniel Okafor")[0]
    texts = [paragraph.text for paragraph in ceo_prepared.paragraphs]
    assert any(text.endswith("Helen Ortiz and her team closed the books two days earlier than last year.") for text in texts)
    assert any(text.startswith("Helen Ortiz, our Chief Financial Officer, will now walk") for text in texts)
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
    assert "Grace Lin" not in {segment.speaker for segment in result.segments}
    assert (
        f"Possible speaker line not recognised: 'Grace Lin' (line {line_no}), "
        "text attributed to Helen M. Ortiz"
    ) in result.warnings
    assert not any("Possible speaker line" in warning for warning in parse_file(kestrel_path).warnings)


@pytest.mark.parametrize("line", ["END OF TRANSCRIPT", "End of Transcript", "[END]", "-- End --"])
def test_end_marker_matches(line):
    assert END_MARKER.fullmatch(line)


@pytest.mark.parametrize("line", ["The end of the quarter was strong.", "Ending remarks", "Weekend"])
def test_end_marker_ignores_ordinary_lines(line):
    assert not END_MARKER.fullmatch(line)


def test_parsing_stops_at_end_marker(meridian):
    last = meridian.segments[-1]
    assert last.speaker == "Operator"
    assert "END OF TRANSCRIPT" not in segment_text(last, include_boilerplate=True)
    assert not any("mid-sentence" in warning for warning in meridian.warnings)


def test_roles_come_from_participant_list(parsed):
    assert parsed.roster_source == "participant_list"
    roles = {segment.speaker: segment.role for segment in parsed.segments}
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
    roles = {segment.speaker: segment.role for segment in result.segments}
    assert roles == {
        "Operator": "operator",
        "Tom Reyes": "management",
        "Ana Lopez": "management",
        "Raj Patel": "analyst",
        "Kim Wu": "analyst",
        "Mark Stone": "unknown",  # speaks only in Q&A and is never introduced
    }
    assert result.unknown_speakers == ["Mark Stone"]
    assert [segment.section for segment in result.segments] == ["prepared"] * 3 + ["qa"] * 7
    assert "Tom Reyes: that label" in segment_text(result.segments[2])
    assert any("No participant list" in warning for warning in result.warnings)
    assert any("Mark Stone" in warning for warning in result.warnings)


def test_unidentified_analyst_is_unknown_with_warning(kestrel_text):
    text = kestrel_text.replace("Claire Dubois\n\nCan you", "Unidentified Analyst\n\nCan you")
    result = parse_transcript(text)
    roles = {segment.speaker: segment.role for segment in result.segments}
    assert roles["Unidentified Analyst"] == "unknown"
    assert result.unknown_speakers == ["Unidentified Analyst"]
    assert "Could not determine role for: Unidentified Analyst" in result.warnings
