from pathlib import Path

from parsing.header import read_call_date, read_call_title
from parsing.parser import parse_file, parse_transcript
from tests.parsing.test_one_line_per_paragraph import REAL_STYLE

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_meridian_header_skips_the_capital_letter_notice():
    parsed = parse_file(FIXTURES / "meridian.txt")
    assert parsed.header[0] == "SYNTHETIC TEST FIXTURE - NOT A REAL COMPANY OR EARNINGS CALL"
    assert parsed.call_title == "Meridian Cloud Systems plc · Q2 2026 Earnings Conference Call"
    assert parsed.call_date == "August 6, 2026"
    assert "CORPORATE PARTICIPANTS" not in parsed.header  # the header ends where the participant list starts


def test_northwind_header():
    parsed = parse_file(FIXTURES / "sample_northwind_q3fy26.txt")
    assert parsed.call_title == "Northwind Robotics, Inc. (NWRB) · Q3 Fiscal 2026 Earnings Conference Call"
    assert parsed.call_date == "October 22, 2026"


def test_header_without_a_participant_list_ends_at_the_first_speaker():
    text = REAL_STYLE.replace("Jane Doe, John Roe\n", "Jane Doe, John Roe\nWednesday July 29, 2026\n")
    parsed = parse_transcript(text)
    assert parsed.header == ["Acme Corp FY26 Fourth Quarter Earnings Conference Call",
                             "Jane Doe, John Roe", "Wednesday July 29, 2026"]
    assert parsed.call_title == "Acme Corp FY26 Fourth Quarter Earnings Conference Call"
    assert parsed.call_date == "July 29, 2026"


def test_no_title_or_date_in_the_header():
    assert read_call_title(["Some notes", "More notes"]) is None
    assert read_call_date(["Some notes"]) is None
