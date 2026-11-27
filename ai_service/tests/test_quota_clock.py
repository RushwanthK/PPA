"""Quota days follow Gemini's reset (midnight Pacific) and are shown in IST."""

from datetime import date, datetime, timezone

from app.assistant.quota_clock import format_ist, next_reset, quota_day, seconds_until_reset

UTC = timezone.utc


def test_winter_reset_is_1_30_pm_ist():
    now = datetime(2026, 11, 24, 6, 0, tzinfo=UTC)          # 11:30 AM IST, 10 PM Pacific on the 23rd
    assert quota_day(now) == date(2026, 11, 23)
    assert next_reset(now).isoformat() == "2026-11-24T13:30:00+05:30"
    assert seconds_until_reset(now) == 2 * 3600


def test_summer_reset_is_12_30_pm_ist():
    now = datetime(2026, 7, 1, 3, 0, tzinfo=UTC)              # daylight saving in California
    assert next_reset(now).isoformat() == "2026-07-01T12:30:00+05:30"


def test_day_changes_exactly_at_pacific_midnight():
    assert quota_day(datetime(2026, 11, 24, 7, 59, tzinfo=UTC)) == date(2026, 11, 23)
    assert quota_day(datetime(2026, 11, 24, 8, 0, tzinfo=UTC)) == date(2026, 11, 24)


def test_format_ist_adds_the_date_only_when_not_today():
    now = datetime(2026, 11, 24, 6, 0, tzinfo=UTC)
    assert format_ist(next_reset(now), now) == "1:30 PM IST"
    later = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)          # 3:30 PM IST, after today's reset
    assert format_ist(next_reset(later), later) == "1:30 PM IST on 25 Nov"
