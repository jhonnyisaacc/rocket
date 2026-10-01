"""Black-Scholes puts. Used only as a documented approximation for BTC options."""

from __future__ import annotations

import math


def norm_cdf(x: float) -> float:
    """Abramowitz and Stegun 26.2.17. Accurate to about 7.5e-8."""
    if x < 0:
        return 1.0 - norm_cdf(-x)
    t = 1.0 / (1.0 + 0.2316419 * x)
    density = 0.3989422804014327 * math.exp(-0.5 * x * x)
    poly = t * (
        0.319381530
        + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429)))
    )
    return 1.0 - density * poly


def bs_put(spot: float, strike: float, years: float, iv: float, rate: float) -> float:
    if spot <= 0 or strike <= 0:
        return 0.0
    if years <= 0 or iv <= 0:
        discounted = strike * math.exp(-rate * max(years, 0.0))
        return max(discounted - spot, 0.0)
    sigma = iv * math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * years) / sigma
    d2 = d1 - sigma
    return strike * math.exp(-rate * years) * norm_cdf(-d2) - spot * norm_cdf(-d1)
