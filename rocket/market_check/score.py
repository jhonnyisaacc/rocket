"""Pillar colors and the risk regime. Pure: the panel view is the only input."""

from __future__ import annotations

from datetime import date
from typing import Any

from rocket.market_check.calendar import events_on, upcoming
from rocket.market_check.config import Config
from rocket.market_check.mathutil import (
    color_change,
    color_high_bad,
    level_change,
    pct_change,
    realized_vol,
    sma,
)
from rocket.market_check.panel import AsOfView, SeriesPanel

COLOR_VALUE = {"green": 1.0, "yellow": 0.0, "red": -1.0}
PILLAR_ORDER = ("rates", "oil", "volatility", "credit", "dollar_gold", "crypto")


def _sub(name: str, color: str, value: float | None, rule: str) -> dict[str, Any]:
    return {"name": name, "color": color, "value": value, "rule": rule}


def _rollup(subs: list[dict[str, Any]], config: Config) -> dict[str, Any]:
    if not subs:
        return {"color": "missing", "score": None, "subs": []}
    score = sum(COLOR_VALUE[item["color"]] for item in subs) / len(subs)
    if score >= config.rollup.green_min:
        color = "green"
    elif score <= config.rollup.red_max:
        color = "red"
    else:
        color = "yellow"
    return {"color": color, "score": score, "subs": subs}


def _rates(view: AsOfView, config: Config) -> dict[str, Any]:
    rules = config.rates
    window = config.windows.trend
    subs: list[dict[str, Any]] = []
    y10 = view.closes("yield_10y")
    y30 = view.closes("yield_30y")
    y2 = view.closes("yield_2y")
    funds = view.value("fed_funds")
    if y10:
        subs.append(_sub(
            "yield_10y_level",
            color_high_bad(y10[-1], rules.yield_10y_green_max, rules.yield_10y_red_min),
            y10[-1],
            f"green below {rules.yield_10y_green_max}; red above {rules.yield_10y_red_min}",
        ))
        change = level_change(y10, window)
        if change is not None:
            subs.append(_sub(
                "yield_10y_trend",
                color_change(change, green_below=-rules.trend_abs, red_above=rules.trend_abs),
                change,
                f"{window}-session change; red at or above +{rules.trend_abs} points",
            ))
    if y30:
        subs.append(_sub(
            "yield_30y_level",
            color_high_bad(y30[-1], rules.yield_30y_green_max, rules.yield_30y_red_min),
            y30[-1],
            f"green below {rules.yield_30y_green_max}; red above {rules.yield_30y_red_min}",
        ))
        change = level_change(y30, window)
        if change is not None:
            subs.append(_sub(
                "yield_30y_trend",
                color_change(change, green_below=-rules.trend_abs, red_above=rules.trend_abs),
                change,
                f"{window}-session change; red at or above +{rules.trend_abs} points",
            ))
    if y10 and y2:
        spread = y10[-1] - y2[-1]
        high_10y = y10[-1] > rules.yield_10y_red_min
        if spread < rules.curve_invert_red or (spread > rules.curve_stress_red and high_10y):
            color = "red"
        elif 0 <= spread <= rules.curve_healthy_max:
            color = "green"
        else:
            color = "yellow"
        subs.append(_sub(
            "curve_2s10s", color, spread,
            f"10y-2y; red below {rules.curve_invert_red} or above {rules.curve_stress_red} with a red 10y",
        ))
    if y2 and funds is not None:
        pressure = y2[-1] - funds
        if pressure > rules.hike_spread_red:
            color = "red"
        elif pressure < rules.cut_spread_green:
            color = "green"
        else:
            color = "yellow"
        subs.append(_sub(
            "fed_pressure", color, pressure,
            f"2y minus fed funds; red above {rules.hike_spread_red} (hike pressure), green below {rules.cut_spread_green}",
        ))
    return _rollup(subs, config)


def _oil(view: AsOfView, config: Config) -> tuple[dict[str, Any], bool]:
    rules = config.oil
    subs: list[dict[str, Any]] = []
    wti = view.closes("wti")
    brent = view.closes("brent")
    shock = False
    if wti:
        subs.append(_sub(
            "wti_level", color_high_bad(wti[-1], rules.wti_green_max, rules.wti_red_min), wti[-1],
            f"green below {rules.wti_green_max}; red above {rules.wti_red_min}",
        ))
        move = pct_change(wti, config.windows.trend)
        if move is not None:
            subs.append(_sub(
                "wti_momentum",
                color_change(move, green_below=rules.momentum_green, red_above=rules.momentum_red),
                move, f"{config.windows.trend}-session return",
            ))
        jump = pct_change(wti, config.windows.shock)
        shock = jump is not None and jump >= rules.shock_return
    if brent:
        subs.append(_sub(
            "brent_level",
            color_high_bad(brent[-1], rules.brent_green_max, rules.brent_red_min),
            brent[-1],
            f"green below {rules.brent_green_max}; red above {rules.brent_red_min}",
        ))
    return _rollup(subs, config), shock


def _volatility(view: AsOfView, config: Config) -> dict[str, Any]:
    rules = config.volatility
    subs: list[dict[str, Any]] = []
    vix = view.value("vix")
    if vix is not None:
        subs.append(_sub(
            "vix", color_high_bad(vix, rules.vix_green_max, rules.vix_red_min), vix,
            f"green below {rules.vix_green_max}; red above {rules.vix_red_min}",
        ))
    rv = realized_vol(view.closes("tlt"), config.windows.rv)
    if rv is not None:
        subs.append(_sub(
            "move_proxy_tlt_rv",
            color_high_bad(rv, rules.tlt_rv_green_max, rules.tlt_rv_red_min),
            rv,
            "20-day annualized TLT realized vol; MOVE itself is not on a free historical feed",
        ))
    return _rollup(subs, config)


def _credit(view: AsOfView, config: Config) -> dict[str, Any]:
    rules = config.credit
    subs: list[dict[str, Any]] = []
    hy = view.closes("hy_oas")
    if hy:
        subs.append(_sub(
            "hy_oas", color_high_bad(hy[-1], rules.hy_green_max, rules.hy_red_min), hy[-1],
            f"FRED BAMLH0A0HYM2 percent; green below {rules.hy_green_max}; red above {rules.hy_red_min}",
        ))
        change = level_change(hy, config.windows.trend)
        if change is not None:
            subs.append(_sub(
                "hy_oas_trend",
                color_change(change, green_below=rules.hy_tighten_green, red_above=rules.hy_widen_red),
                change, f"{config.windows.trend}-session OAS change in percentage points",
            ))
        return _rollup(subs, config)
    hyg = view.closes("hyg")
    lqd = view.closes("lqd")
    if len(hyg) > config.windows.trend and len(lqd) > config.windows.trend and lqd[-1] and lqd[-1 - config.windows.trend]:
        ratio_now = hyg[-1] / lqd[-1]
        ratio_then = hyg[-1 - config.windows.trend] / lqd[-1 - config.windows.trend]
        change = ratio_now / ratio_then - 1
        subs.append(_sub(
            "hyg_lqd_fallback",
            color_change(change, green_below=rules.hyg_lqd_green, red_above=rules.hyg_lqd_red),
            change,
            "HY OAS missing; 20-session HYG/LQD return is the credit proxy",
        ))
    return _rollup(subs, config)


def _dollar_gold(view: AsOfView, config: Config) -> dict[str, Any]:
    rules = config.dollar_gold
    subs: list[dict[str, Any]] = []
    dollar = pct_change(view.closes("dollar"), config.windows.trend)
    if dollar is not None:
        subs.append(_sub(
            "dollar_trend",
            color_change(dollar, green_below=rules.dxy_trend_green, red_above=rules.dxy_trend_red),
            dollar, f"{config.windows.trend}-session dollar return; a rising dollar is red",
        ))
    gold = pct_change(view.closes("gold"), config.windows.trend)
    if gold is not None:
        if gold >= rules.gold_stress:
            color = "red"
        elif gold <= -rules.gold_stress:
            color = "yellow"
        else:
            color = "green"
        subs.append(_sub(
            "gold_trend", color, gold,
            f"red when gold is up at least {rules.gold_stress:.0%} over {config.windows.trend} sessions (stress bid)",
        ))
    return _rollup(subs, config)


def _funding_sum(view: AsOfView, days: int) -> float | None:
    rows = view.history("funding_daily")
    if not rows:
        return None
    end = rows[-1][0]
    start = end.fromordinal(end.toordinal() - days + 1)
    sample = [value for day, value in rows if day >= start]
    if not sample:
        return None
    return sum(sample)


def _crypto(view: AsOfView, config: Config) -> dict[str, Any]:
    rules = config.crypto
    subs: list[dict[str, Any]] = []
    closes = view.closes("btc")
    fast = sma(closes, config.windows.sma_fast)
    slow = sma(closes, config.windows.sma_slow)
    trend = "missing"
    if closes and slow is not None:
        price = closes[-1]
        if price > slow and (fast is None or price >= fast):
            trend = "green"
        elif price > slow:
            trend = "yellow"
        else:
            trend = "red"
        subs.append(_sub(
            "btc_trend", trend, price,
            f"green above the {config.windows.sma_fast} and {config.windows.sma_slow} session averages; red below the slow average",
        ))
    funding = _funding_sum(view, config.windows.funding_days)
    if funding is not None:
        if funding < rules.funding_panic or (funding > rules.funding_hot and trend == "red"):
            color = "red"
        elif funding > rules.funding_hot or funding < rules.funding_cold:
            color = "yellow"
        else:
            color = "green"
        subs.append(_sub(
            "funding", color, funding,
            f"{config.windows.funding_days}-day sum of hourly perp funding; hot above {rules.funding_hot}",
        ))
    dvol = view.value("dvol")
    if dvol is None:
        realized = realized_vol(closes, config.windows.rv)
        dvol = None if realized is None else realized * 100
        dvol_rule = "DVOL missing; 20-day BTC realized vol (percent) stands in"
    else:
        dvol_rule = f"Deribit DVOL; cheap below {rules.dvol_cheap_max}; expensive above {rules.dvol_expensive_min}"
    if dvol is not None:
        subs.append(_sub(
            "options_vol",
            color_high_bad(dvol, rules.dvol_cheap_max, rules.dvol_expensive_min),
            dvol, dvol_rule,
        ))
    rolled = _rollup(subs, config)
    rolled["trend"] = trend
    rolled["dvol"] = dvol
    rolled["fast"] = fast
    rolled["slow"] = slow
    rolled["price"] = closes[-1] if closes else None
    return rolled


def combine_regime(pillars: dict[str, dict[str, Any]], config: Config) -> tuple[str, float | None]:
    known = [name for name in PILLAR_ORDER if pillars[name]["color"] != "missing"]
    if pillars["rates"]["color"] == "missing" or len(known) < config.regime.min_pillars:
        return "unknown", None
    total = sum(config.regime.weights[name] * COLOR_VALUE[pillars[name]["color"]] for name in known)
    rates = pillars["rates"]["color"]
    vol = pillars["volatility"]["color"]
    credit = pillars["credit"]["color"]
    if total <= config.regime.risk_off_max or (rates == "red" and (vol == "red" or credit == "red")):
        return "risk-off", total
    if total >= config.regime.risk_on_min and rates != "red" and vol != "red":
        return "risk-on", total
    return "neutral", total


def score_asof(panel: SeriesPanel, day: date, config: Config) -> dict[str, Any]:
    """Score `day` using only data the panel exposes on that day."""
    view = panel.asof(day, config.lags)
    oil, shock = _oil(view, config)
    pillars = {
        "rates": _rates(view, config),
        "oil": oil,
        "volatility": _volatility(view, config),
        "credit": _credit(view, config),
        "dollar_gold": _dollar_gold(view, config),
        "crypto": _crypto(view, config),
    }
    regime, total = combine_regime(pillars, config)
    today = events_on(day, config)
    ahead = upcoming(day, config, config.events.horizon_days)
    return {
        "date": day.isoformat(),
        "regime": regime,
        "score": total,
        "pillars": pillars,
        "oil_shock": shock,
        "events_today": today,
        "events_upcoming": ahead,
        "regime_rule": (
            "Weighted pillar scores. Risk-off when the total is at or below "
            f"{config.regime.risk_off_max} or when rates are red and volatility or credit is also red. "
            f"Risk-on when the total is at least {config.regime.risk_on_min} and neither rates nor "
            "volatility is red. Otherwise neutral. Unknown when rates are missing or fewer than "
            f"{config.regime.min_pillars} pillars have data."
        ),
    }
