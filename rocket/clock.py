"""US listed equity session clocks. Daily dates are session labels, never retrieval times."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from rocket.pit import parse_datetime

NY = ZoneInfo("America/New_York")


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    return current - timedelta(days=(current.weekday() - weekday) % 7)


def _observed_fixed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _easter_sunday(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def exchange_holidays(year: int) -> set[date]:
    days = {
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter_sunday(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed_fixed(date(year, 6, 19)),
        _observed_fixed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed_fixed(date(year, 12, 25)),
    }
    for y in (year, year + 1):
        day = date(y, 1, 1)
        if day.weekday() != 5:
            days.add(_observed_fixed(day))
    return days


def session_day(day: date) -> bool:
    return day.weekday() < 5 and day not in exchange_holidays(day.year)


def session_close(day: date) -> datetime:
    thanksgiving = _nth_weekday(day.year, 11, 3, 4)
    early = day == thanksgiving + timedelta(days=1) or (day.month, day.day) in {(7, 3), (12, 24)}
    return datetime.combine(day, time(13 if early else 16), NY)


def latest_completed_session(now: datetime) -> date:
    local = now.astimezone(NY)
    day = local.date()
    if local < session_close(day) + timedelta(minutes=20):
        day -= timedelta(days=1)
    while not session_day(day):
        day -= timedelta(days=1)
    return day


def equity_observation_fresh(value: str | None, now: datetime, *, daily: bool = True) -> bool:
    try:
        stamp = parse_datetime(value)
        if stamp is None or stamp > now:
            return False
        day = stamp.date() if daily else stamp.astimezone(NY).date()
        if not session_day(day) or day < latest_completed_session(now):
            return False
        local = now.astimezone(NY)
        if (
            not daily
            and session_day(local.date())
            and time(9, 50) <= local.time() < session_close(local.date()).time()
        ):
            return now - stamp <= timedelta(minutes=20)
        return True
    except (ValueError, TypeError):
        return False
