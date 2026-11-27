"""When "today" starts and ends for quotas, and how reset times are shown to users.

Our per-user daily limits reset at the same moment as the Gemini free tier: midnight
Pacific time (Gemini's documented daily reset). Users in India see that moment in IST:
1:30 PM IST in winter (PST) and 12:30 PM IST in summer (PDT). zoneinfo handles the
daylight-saving switch; on Windows it needs the `tzdata` package.

Groq's daily limits use a rolling window instead of a fixed reset, and its 429 replies
say how long to wait, so they are handled from the reply itself.
"""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

PROVIDER_TZ = ZoneInfo("America/Los_Angeles")
IST = timezone(timedelta(hours=5, minutes=30), "IST")  # no daylight saving, so a fixed offset is exact


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def quota_day(now: datetime | None = None) -> date:
    """The quota 'day': the calendar date in Pacific time."""
    return _now(now).astimezone(PROVIDER_TZ).date()


def next_reset(now: datetime | None = None) -> datetime:
    """The next Pacific midnight, as an IST datetime."""
    local = _now(now).astimezone(PROVIDER_TZ)
    midnight = datetime.combine(local.date() + timedelta(days=1), time(0), tzinfo=PROVIDER_TZ)
    return midnight.astimezone(IST)


def seconds_until_reset(now: datetime | None = None) -> int:
    now = _now(now)
    return max(1, int((next_reset(now) - now).total_seconds()))


def format_ist(moment: datetime, now: datetime | None = None) -> str:
    """'1:30 PM IST', with the date added when it is not today in India: '1:30 PM IST on 26 Nov'."""
    moment = moment.astimezone(IST)
    hour = moment.hour % 12 or 12
    text = f"{hour}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'} IST"
    if moment.date() != _now(now).astimezone(IST).date():
        text += f" on {moment.day} {moment.strftime('%b')}"
    return text
