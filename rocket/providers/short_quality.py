"""Explainable short-quality factors. Missing stays UNKNOWN; never inferred from today."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

FLAT_REVISION_BAND = 0.005
RETEST_WINDOW = 10
BREAKDOWN_LOOKBACK = 20
RELATIVE_WINDOWS = (20, 60)


def _finite(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive(value: Any) -> float | None:
    number = _finite(value)
    return number if number is not None and number > 0 else None


def window_return(closes: Sequence[Any] | None, window: int = 20) -> float | None:
    if closes is None or window <= 0 or len(closes) < window + 1:
        return None
    start = _positive(closes[-(window + 1)])
    end = _positive(closes[-1])
    if start is None or end is None:
        return None
    return end / start - 1


def relative_strength(
    stock: Sequence[Any] | None,
    sector: Sequence[Any] | None,
    market: Sequence[Any] | None,
    *,
    window: int = 20,
) -> dict[str, Any]:
    stock_ret = window_return(stock, window)
    sector_ret = window_return(sector, window)
    market_ret = window_return(market, window)
    vs_sector = None if stock_ret is None or sector_ret is None else stock_ret - sector_ret
    vs_market = None if stock_ret is None or market_ret is None else stock_ret - market_ret
    confirmation = None if vs_sector is None or vs_market is None else vs_sector < 0 and vs_market < 0
    return {
        "window": window,
        "stock_return": stock_ret,
        "sector_return": sector_ret,
        "market_return": market_ret,
        "relative_vs_sector": vs_sector,
        "relative_vs_market": vs_market,
        "underperforms_both": confirmation,
        "state": "UNKNOWN" if stock_ret is None or sector_ret is None or market_ret is None else "OBSERVED",
    }


def relative_weakness_flag(row: Mapping[str, Any], *, threshold: float = 0.0) -> bool | None:
    vs_sector = _finite(row.get("relative_vs_sector"))
    vs_market = _finite(row.get("relative_vs_market"))
    if vs_sector is None or vs_market is None:
        return None
    return vs_sector < threshold and vs_market < threshold


def prior_session_low(closes: Sequence[Any] | None, lookback: int = BREAKDOWN_LOOKBACK) -> float | None:
    if closes is None or len(closes) < lookback + 1:
        return None
    window = [_positive(value) for value in closes[-(lookback + 1):-1]]
    if any(value is None for value in window):
        return None
    return min(window)  # type: ignore[type-var]


def prior_session_high(closes: Sequence[Any] | None, lookback: int = BREAKDOWN_LOOKBACK) -> float | None:
    if closes is None or len(closes) < lookback + 1:
        return None
    window = [_positive(value) for value in closes[-(lookback + 1):-1]]
    if any(value is None for value in window):
        return None
    return max(window)  # type: ignore[type-var]


def breakdown(closes: Sequence[Any] | None, lookback: int = BREAKDOWN_LOOKBACK) -> bool | None:
    low = prior_session_low(closes, lookback)
    last = _positive(closes[-1] if closes else None)
    if low is None or last is None:
        return None
    return last < low


def failed_retest(
    closes: Sequence[Any] | None,
    *,
    lookback: int = BREAKDOWN_LOOKBACK,
    retest_window: int = RETEST_WINDOW,
) -> dict[str, Any]:
    """Close-only failed retest.

    1. A session closes below its prior `lookback`-session low (breakdown).
    2. A later session closes back at or above that broken low (retest).
    3. The latest session closes back below the broken low (failure).
    """
    if closes is None or len(closes) < lookback + 2:
        return {"state": "UNKNOWN", "failed_retest": None, "breakdown_index": None, "broken_low": None}
    last = len(closes) - 1
    start = max(lookback, last - retest_window)
    for index in range(start, last):
        prior = [_positive(value) for value in closes[index - lookback:index]]
        close = _positive(closes[index])
        if close is None or any(value is None for value in prior):
            continue
        broken = min(prior)  # type: ignore[type-var]
        if close >= broken:
            continue
        retested = False
        for later in range(index + 1, last):
            later_close = _positive(closes[later])
            if later_close is None:
                continue
            if later_close >= broken:
                retested = True
        fail_close = _positive(closes[last])
        if retested and fail_close is not None and fail_close < broken:
            return {
                "state": "OBSERVED",
                "failed_retest": True,
                "breakdown_index": index,
                "broken_low": broken,
                "rule": "breakdown, close back to broken low, latest close fails back below",
            }
    if breakdown(closes, lookback) is None:
        return {"state": "UNKNOWN", "failed_retest": None, "breakdown_index": None, "broken_low": None}
    return {
        "state": "OBSERVED",
        "failed_retest": False,
        "breakdown_index": None,
        "broken_low": prior_session_low(closes, lookback),
        "rule": "breakdown, close back to broken low, latest close fails back below",
    }


def moving_average(closes: Sequence[Any] | None, window: int = 20) -> float | None:
    if closes is None or len(closes) < window:
        return None
    values = [_positive(value) for value in closes[-window:]]
    if any(value is None for value in values):
        return None
    return sum(values) / window  # type: ignore[arg-type]


def classify_regime(spy: Sequence[Any] | None, sector: Sequence[Any] | None, *, window: int = 20) -> dict[str, Any]:
    """Regime is a risk modifier, not a stock-idea generator."""
    spy_last = _positive(spy[-1] if spy else None)
    sector_last = _positive(sector[-1] if sector else None)
    spy_ma = moving_average(spy, window)
    sector_ma = moving_average(sector, window)
    if spy_last is None or spy_ma is None or sector_last is None or sector_ma is None:
        return {
            "regime": "UNKNOWN",
            "spy_vs_ma": None,
            "sector_vs_ma": None,
            "risk_class": "UNKNOWN",
        }
    spy_below = spy_last < spy_ma
    sector_below = sector_last < sector_ma
    if spy_below and sector_below:
        regime = "SHORT_FRIENDLY"
        risk_class = "standard"
    elif (not spy_below) and (not sector_below):
        regime = "SHORT_HOSTILE"
        risk_class = "unattractive"
    else:
        regime = "NEUTRAL"
        risk_class = "elevated"
    return {
        "regime": regime,
        "spy_vs_ma": spy_last / spy_ma - 1,
        "sector_vs_ma": sector_last / sector_ma - 1,
        "risk_class": risk_class,
    }


def risk_reward(entry: Any, invalidation: Any, target: Any) -> dict[str, Any]:
    """Short R/R. Missing or non-defensible targets stay UNKNOWN."""
    price = _positive(entry)
    stop = _positive(invalidation)
    downside = _positive(target)
    if price is None or stop is None or downside is None:
        return {
            "current_price": price,
            "entry": price,
            "invalidation": stop,
            "target": downside,
            "risk": None,
            "reward": None,
            "reward_to_risk": "UNKNOWN",
        }
    risk = stop - price
    reward = price - downside
    if risk <= 0 or reward <= 0:
        return {
            "current_price": price,
            "entry": price,
            "invalidation": stop,
            "target": downside,
            "risk": risk,
            "reward": reward,
            "reward_to_risk": "UNKNOWN",
        }
    return {
        "current_price": price,
        "entry": price,
        "invalidation": stop,
        "target": downside,
        "risk": risk,
        "reward": reward,
        "reward_to_risk": reward / risk,
    }


def select_downside_target(
    closes: Sequence[Any] | None,
    *,
    opens: Sequence[Any] | None = None,
    near_band: float = 0.02,
    support_window: int = 60,
    swing_window: int = 120,
    gap_band: float = 0.03,
) -> dict[str, Any]:
    """Defensible short target. Never the multi-year lowest close.

    Preference:
    1. nearest meaningful prior support (local trough) within 60 sessions
    2. prior 120-session swing low
    3. origin of a recent close-to-close or open gap
    """
    empty = {"target": None, "rule": None, "state": "UNKNOWN"}
    if closes is None or len(closes) < 3:
        return empty
    last = _positive(closes[-1])
    if last is None:
        return empty
    ceiling = last * (1 - near_band)

    def _window(values: Sequence[Any], length: int) -> list[float]:
        prior = values[:-1]
        slice_ = prior[-length:] if len(prior) > length else prior
        return [number for number in (_positive(value) for value in slice_) if number is not None]

    support = _window(closes, support_window)
    troughs = []
    for index in range(1, len(support) - 1):
        left, mid, right = support[index - 1], support[index], support[index + 1]
        if mid < left and mid < right and mid < ceiling:
            troughs.append(mid)
    if troughs:
        target = max(troughs)
        return {"target": target, "rule": "prior_support_60", "state": "OBSERVED"}

    swing = _window(closes, swing_window)
    if swing:
        floor = min(swing)
        if floor < ceiling:
            return {"target": floor, "rule": "swing_low_120", "state": "OBSERVED"}

    lookback = min(len(closes) - 1, support_window)
    for index in range(len(closes) - 1, len(closes) - 1 - lookback, -1):
        prev_close = _positive(closes[index - 1])
        this_close = _positive(closes[index])
        this_open = _positive(opens[index]) if opens is not None and index < len(opens) else None
        gapped = False
        origin = None
        if prev_close is not None and this_close is not None and this_close <= prev_close * (1 - gap_band):
            gapped, origin = True, prev_close
        if prev_close is not None and this_open is not None and this_open <= prev_close * (1 - gap_band):
            gapped, origin = True, prev_close
        if gapped and origin is not None and origin < ceiling:
            return {"target": origin, "rule": "event_gap_origin", "state": "OBSERVED"}
    return empty


def history_target(
    closes: Sequence[Any] | None,
    *,
    opens: Sequence[Any] | None = None,
    near_band: float = 0.02,
    support_window: int = 60,
    swing_window: int = 120,
) -> float | None:
    return select_downside_target(
        closes,
        opens=opens,
        near_band=near_band,
        support_window=support_window,
        swing_window=swing_window,
    )["target"]


def research_entry_price(*, signal_close: Any, next_open: Any, mode: str = "CLOSE_SIGNAL") -> dict[str, Any]:
    """Close-of-signal is optimistic; next-session open is the realistic alternative."""
    if mode == "CLOSE_SIGNAL":
        price = _positive(signal_close)
        return {"entry": price, "mode": "CLOSE_SIGNAL", "state": "UNKNOWN" if price is None else "OBSERVED"}
    price = _positive(next_open)
    return {"entry": price, "mode": "NEXT_SESSION_OPEN", "state": "UNKNOWN" if price is None else "OBSERVED"}


def quality_state(latest: Any, prior: Any, *, falling_is_deteriorating: bool = True) -> str:
    left, right = _finite(latest), _finite(prior)
    if left is None or right is None:
        return "UNKNOWN"
    if left == right:
        return "FLAT"
    worse = left < right if falling_is_deteriorating else left > right
    return "DETERIORATING" if worse else "IMPROVING"


def cash_flow_quality(latest: Mapping[str, Any] | None, prior: Mapping[str, Any] | None) -> dict[str, Any]:
    """Two-period statement comparison. Incompatible or missing periods stay UNKNOWN."""
    if not isinstance(latest, Mapping) or not isinstance(prior, Mapping):
        return {
            "ocf_trend": "UNKNOWN",
            "ni_vs_ocf": "UNKNOWN",
            "share_dilution": "UNKNOWN",
            "margin_trend": "UNKNOWN",
            "state": "UNKNOWN",
        }
    if latest.get("fiscal_year") == prior.get("fiscal_year") and latest.get("period_end") == prior.get("period_end"):
        return {
            "ocf_trend": "UNKNOWN",
            "ni_vs_ocf": "UNKNOWN",
            "share_dilution": "UNKNOWN",
            "margin_trend": "UNKNOWN",
            "state": "UNKNOWN",
            "reason": "incompatible_or_identical_fiscal_period",
        }
    ocf_trend = quality_state(latest.get("operating_cash_flow"), prior.get("operating_cash_flow"))
    ni_latest, ni_prior = _finite(latest.get("net_income")), _finite(prior.get("net_income"))
    ocf_latest, ocf_prior = _finite(latest.get("operating_cash_flow")), _finite(prior.get("operating_cash_flow"))
    if None in (ni_latest, ni_prior, ocf_latest, ocf_prior):
        ni_vs_ocf = "UNKNOWN"
    elif ni_latest > ni_prior and ocf_latest < ocf_prior:
        ni_vs_ocf = "DETERIORATING"
    elif ni_latest < ni_prior and ocf_latest > ocf_prior:
        ni_vs_ocf = "IMPROVING"
    else:
        ni_vs_ocf = "FLAT"
    shares_latest, shares_prior = _positive(latest.get("diluted_shares")), _positive(prior.get("diluted_shares"))
    if shares_latest is None or shares_prior is None:
        dilution = "UNKNOWN"
    elif shares_latest > shares_prior * 1.02:
        dilution = "DETERIORATING"
    elif shares_latest < shares_prior * 0.98:
        dilution = "IMPROVING"
    else:
        dilution = "FLAT"
    margin_trend = quality_state(latest.get("operating_margin"), prior.get("operating_margin"))
    observed = [state for state in (ocf_trend, ni_vs_ocf, dilution, margin_trend) if state != "UNKNOWN"]
    if not observed:
        overall = "UNKNOWN"
    elif "DETERIORATING" in observed:
        overall = "DETERIORATING"
    elif all(state == "IMPROVING" for state in observed):
        overall = "IMPROVING"
    else:
        overall = "FLAT"
    return {
        "ocf_trend": ocf_trend,
        "ni_vs_ocf": ni_vs_ocf,
        "share_dilution": dilution,
        "margin_trend": margin_trend,
        "state": overall,
        "latest_period": latest.get("period_end"),
        "prior_period": prior.get("period_end"),
    }


def revision_state(later: Any, earlier: Any, *, band: float = FLAT_REVISION_BAND) -> dict[str, Any]:
    left, right = _finite(later), _finite(earlier)
    if left is None or right is None or right == 0:
        return {"state": "UNKNOWN", "change": None}
    change = (left - right) / abs(right)
    if abs(change) < band:
        state = "FLAT"
    elif change < 0:
        state = "DETERIORATING"
    else:
        state = "IMPROVING"
    return {"state": state, "change": change}


def forward_excursions(entry: Any, highs: Sequence[Any], lows: Sequence[Any], closes: Sequence[Any]) -> dict[str, Any]:
    price = _positive(entry)
    if price is None or not closes:
        return {
            "underlying_returns": [],
            "short_returns": [],
            "mae": None,
            "mfe": None,
            "max_mae": None,
            "max_favorable_move": None,
        }
    underlying = []
    for close in closes:
        value = _positive(close)
        underlying.append(None if value is None else value / price - 1)
    short = [None if value is None else -value for value in underlying]
    adverse = []
    favorable = []
    for high, low in zip(highs or closes, lows or closes, strict=False):
        high_n, low_n = _positive(high), _positive(low)
        if high_n is not None:
            adverse.append(high_n / price - 1)
        if low_n is not None:
            favorable.append(1 - low_n / price)
    mae = max(adverse) if adverse else None
    mfe = max(favorable) if favorable else None
    return {
        "underlying_returns": underlying,
        "short_returns": short,
        "mae": mae,
        "mfe": mfe,
        "max_mae": mae,
        "max_favorable_move": mfe,
    }
