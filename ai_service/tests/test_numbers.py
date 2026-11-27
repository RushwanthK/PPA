"""Number grounding for my-data answers."""

from app.assistant.numbers import numbers_in_answer, unverified_numbers

DATA = '{"facts":{"expense_total":12345.67,"count":14,"share_pct":37.5}}'


def test_indian_and_western_grouping_are_read():
    assert numbers_in_answer("You spent ₹1,23,456.50 and ₹123,456") == [123456.5, 123456.0]


def test_figures_from_the_data_pass_including_roundings():
    assert unverified_numbers("You spent ₹12,345.67 (about ₹12,346) in 14 transactions, 37.5% of spending.",
                              DATA) == []


def test_invented_or_calculated_numbers_are_caught():
    assert unverified_numbers("You spent ₹12,000 more than last month.", DATA) == [12000.0]
    assert unverified_numbers("That is 12.3 lakh.", DATA) == [12.3]


def test_dates_small_numbers_and_question_numbers_are_allowed():
    text = "Between 1 Nov 2026 and 2026-11-24 (November 2026), your top 3 categories over the last 6 months"
    assert unverified_numbers(text, DATA, "spending over the last 6 months") == []
    assert unverified_numbers("in the last 45 days", DATA) == [45.0]
    assert unverified_numbers("in the last 45 days", DATA, "last 45 days") == []


def test_typographic_hyphens_and_spaces_in_dates():
    # Seen live from gpt-oss on 2026-11-24: non-breaking hyphens inside an ISO date.
    assert numbers_in_answer("from 2026‑11‑01 to 2026‑11‑30: ₹ 2,999") == [2999.0]
