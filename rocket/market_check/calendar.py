"""Static event calendar. FOMC dates are listed; CPI and payrolls follow documented rules."""

from __future__ import annotations

import calendar as calendar_mod
from datetime import date, timedelta

from rocket.market_check.config import Config

# CPI is not pulled from a live BLS feed. Second Wednesday is a stable proxy
# for the usual mid-month release and is labeled as such in the output.
CPI_RULE = "second_wednesday_proxy"
NFP_RULE = "first_friday"


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def first_friday(year: int, month: int) -> date:
    return _nth_weekday(year, month, calendar_mod.FRIDAY, 1)


def second_wednesday(year: int, month: int) -> date:
    return _nth_weekday(year, month, calendar_mod.WEDNESDAY, 2)


def _months(start: date, end: date) -> list[tuple[int, int]]:
    months: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return months


def events_between(start: date, end: date, config: Config) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for day in config.events.fomc:
        if start <= day <= end:
            rows.append({"date": day.isoformat(), "kind": "fomc"})
    for year, month in _months(start, end):
        for kind, stamp in (
            ("cpi", second_wednesday(year, month)),
            ("nfp", first_friday(year, month)),
        ):
            if start <= stamp <= end:
                rows.append({"date": stamp.isoformat(), "kind": kind})
    rows.sort(key=lambda item: (item["date"], item["kind"]))
    return rows


def events_on(day: date, config: Config) -> list[str]:
    return [row["kind"] for row in events_between(day, day, config)]


def upcoming(day: date, config: Config, horizon: int) -> list[dict[str, str | int]]:
    rows = []
    for item in events_between(day, day + timedelta(days=horizon), config):
        stamp = date.fromisoformat(item["date"])
        rows.append({**item, "days": (stamp - day).days})
    return rows
