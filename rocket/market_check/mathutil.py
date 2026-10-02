"""Small numeric helpers. No lookahead: callers pass an already sliced history."""

from __future__ import annotations

import math


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def sample_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    center = sum(values) / len(values)
    var = sum((item - center) ** 2 for item in values) / (len(values) - 1)
    return math.sqrt(var)


def pct_change(closes: list[float], periods: int) -> float | None:
    if periods <= 0 or len(closes) <= periods or closes[-1 - periods] == 0:
        return None
    return closes[-1] / closes[-1 - periods] - 1


def level_change(values: list[float], periods: int) -> float | None:
    if periods <= 0 or len(values) <= periods:
        return None
    return values[-1] - values[-1 - periods]


def sma(closes: list[float], window: int) -> float | None:
    if window <= 0 or len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def realized_vol(closes: list[float], window: int) -> float | None:
    if window < 2 or len(closes) <= window:
        return None
    returns = [closes[index] / closes[index - 1] - 1 for index in range(len(closes) - window, len(closes))]
    sigma = sample_std(returns)
    if sigma is None:
        return None
    return sigma * math.sqrt(252)


def min_close(closes: list[float], window: int) -> float | None:
    if not closes:
        return None
    sample = closes[-window:] if window > 0 else closes
    return min(sample)


def color_high_bad(value: float, green_max: float, red_min: float) -> str:
    if value < green_max:
        return "green"
    if value > red_min:
        return "red"
    return "yellow"


def color_change(value: float, *, green_below: float, red_above: float) -> str:
    if value <= green_below:
        return "green"
    if value >= red_above:
        return "red"
    return "yellow"
