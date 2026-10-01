"""Performance statistics for a daily NAV path."""

from __future__ import annotations

import math
from datetime import date
from itertools import pairwise


def _returns(nav: list[float]) -> list[float]:
    out = []
    for prev, nxt in pairwise(nav):
        out.append(0.0 if prev == 0 else nxt / prev - 1)
    return out


def max_drawdown(nav: list[float]) -> float | None:
    if not nav:
        return None
    peak = nav[0]
    worst = 0.0
    for value in nav:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1)
    return worst


def performance(
    days: list[date],
    nav: list[float],
    *,
    rf_daily: list[float] | None = None,
) -> dict[str, float | None]:
    if len(days) != len(nav) or len(nav) < 2:
        return {"cagr": None, "max_drawdown": None, "volatility": None, "sharpe": None, "total_return": None}
    returns = _returns(nav)
    span = (days[-1] - days[0]).days
    total = nav[-1] / nav[0] - 1 if nav[0] else None
    cagr = None
    if nav[0] > 0 and span > 0 and nav[-1] > 0:
        cagr = (nav[-1] / nav[0]) ** (365.25 / span) - 1
    center = sum(returns) / len(returns)
    var = sum((item - center) ** 2 for item in returns) / (len(returns) - 1) if len(returns) > 1 else 0.0
    vol = math.sqrt(var) * math.sqrt(252) if var > 0 else 0.0
    sharpe = None
    if vol > 0:
        if rf_daily is None:
            excess = returns
        else:
            aligned = rf_daily[: len(returns)]
            excess = [item - rate for item, rate in zip(returns, aligned, strict=False)]
        excess_mean = sum(excess) / len(excess)
        excess_var = sum((item - excess_mean) ** 2 for item in excess) / (len(excess) - 1)
        excess_vol = math.sqrt(excess_var) * math.sqrt(252) if excess_var > 0 else 0.0
        sharpe = None if excess_vol == 0 else (excess_mean * 252) / excess_vol
    return {
        "cagr": cagr,
        "max_drawdown": max_drawdown(nav),
        "volatility": vol,
        "sharpe": sharpe,
        "total_return": total,
    }


def monthly_returns(days: list[date], nav: list[float]) -> list[dict[str, float | str]]:
    if not days:
        return []
    last: dict[tuple[int, int], tuple[date, float]] = {}
    for day, value in zip(days, nav, strict=True):
        last[(day.year, day.month)] = (day, value)
    keys = sorted(last)
    rows = []
    previous = nav[0]
    # The first month's return is versus the first NAV in the path, which is inside that month.
    first_key = keys[0]
    first_day = next(day for day in days if (day.year, day.month) == first_key)
    base = nav[days.index(first_day)]
    previous = base
    for key in keys:
        _, value = last[key]
        ret = 0.0 if previous == 0 else value / previous - 1
        # For the first month, measure from the path start rather than from itself.
        if key == first_key:
            ret = 0.0 if nav[0] == 0 else value / nav[0] - 1
            previous = value
        else:
            previous = value
        rows.append({"month": f"{key[0]:04d}-{key[1]:02d}", "return": ret})
    return rows


def slice_path(
    days: list[date], nav: list[float], start: date, end: date, *, include_prior_base: bool = False,
) -> tuple[list[date], list[float]]:
    chosen = [(day, value) for day, value in zip(days, nav, strict=True) if start <= day <= end]
    if include_prior_base:
        prior = [(day, value) for day, value in zip(days, nav, strict=True) if day < start]
        if prior and chosen:
            chosen = [prior[-1], *chosen]
    if not chosen:
        return [], []
    return [day for day, _ in chosen], [value for _, value in chosen]
