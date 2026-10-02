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
        return {
            "cagr": None,
            "max_drawdown": None,
            "volatility": None,
            "sharpe": None,
            "total_return": None,
        }
    returns = _returns(nav)
    span = (days[-1] - days[0]).days
    total = nav[-1] / nav[0] - 1 if nav[0] else None
    cagr = None
    if nav[0] > 0 and span > 0 and nav[-1] > 0:
        cagr = (nav[-1] / nav[0]) ** (365.25 / span) - 1
    center = sum(returns) / len(returns)
    var = (
        sum((item - center) ** 2 for item in returns) / (len(returns) - 1)
        if len(returns) > 1
        else 0.0
    )
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


def _phi_inv(p: float) -> float:
    """Acklam approximation of the standard normal quantile, for DSR."""
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]
    if p < 0.02425:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p <= 0.97575:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
        )
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
    )


def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def deflated_sharpe(
    observed_sr: float,
    returns: list[float],
    num_trials: int,
) -> dict[str, float | None]:
    """Deflated Sharpe ratio (Bailey & Lopez de Prado 2014).

    `observed_sr` is the annualized Sharpe of `returns` (per-period figures).
    `num_trials` is the number of configurations tried. Returns the benchmark
    Sharpe expected from data mining alone and the probability the observed
    Sharpe clears it.
    """
    freq = 252
    n = len(returns)
    if n < 3 or num_trials < 1:
        return {"benchmark": None, "deflated": None}
    center = sum(returns) / n
    var = sum((item - center) ** 2 for item in returns) / (n - 1)
    if var <= 0:
        return {"benchmark": None, "deflated": None}
    sigma = math.sqrt(var)
    skew = sum((item - center) ** 3 for item in returns) / n / sigma**3
    kurt = sum((item - center) ** 4 for item in returns) / n / sigma**4
    euler = 0.5772156649
    if num_trials < 2:
        # One trial means no selection: the expected max of one draw is zero.
        peak = 0.0
    else:
        peak = (1 - euler) * _phi_inv(1 - 1 / num_trials) + euler * _phi_inv(
            1 - 1 / (num_trials * math.e)
        )
    benchmark = peak * math.sqrt(freq / n)
    denom = math.sqrt(max(1 - skew * observed_sr + (kurt - 1) / 4 * observed_sr**2, 1e-12))
    score = (observed_sr - benchmark) * math.sqrt(n - 1) / denom
    return {"benchmark": benchmark, "deflated": _phi(score)}


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
    days: list[date],
    nav: list[float],
    start: date,
    end: date,
    *,
    include_prior_base: bool = False,
) -> tuple[list[date], list[float]]:
    chosen = [(day, value) for day, value in zip(days, nav, strict=True) if start <= day <= end]
    if include_prior_base:
        prior = [(day, value) for day, value in zip(days, nav, strict=True) if day < start]
        if prior and chosen:
            chosen = [prior[-1], *chosen]
    if not chosen:
        return [], []
    return [day for day, _ in chosen], [value for _, value in chosen]
