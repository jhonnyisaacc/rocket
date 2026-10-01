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
from rocket.market_check.redeploy import is_bottom

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


def _high_points(value: float | None, caution: float, risk: float) -> int:
    if value is None:
        return 0
    if value >= risk:
        return 2
    if value >= caution:
        return 1
    return 0


def _low_points(value: float | None, caution: float, risk: float) -> int:
    """caution is the milder (less negative) cut. risk is the deeper one."""
    if value is None:
        return 0
    if value <= risk:
        return 2
    if value <= caution:
        return 1
    return 0


def stress_score(view: AsOfView, config: Config) -> tuple[float, dict[str, int]]:
    """Composite of rate-of-change stresses. Higher is worse. Levels are the backstop, not the driver."""
    rules = config.regime.stress
    parts: dict[str, int] = {}
    vix = view.closes("vix")
    parts["vix_jump"] = _high_points(level_change(vix, rules.vix_jump_sessions), rules.vix_jump_caution, rules.vix_jump_risk)
    parts["vix_level"] = _high_points(vix[-1] if vix else None, rules.vix_level_caution, rules.vix_level_risk)
    parts["vix"] = min(rules.vix_cap, parts["vix_jump"] + parts["vix_level"])
    hy = view.closes("hy_oas")
    parts["credit"] = _high_points(
        level_change(hy, rules.credit_sessions), rules.credit_widen_caution, rules.credit_widen_risk,
    )
    yields = view.closes("yield_30y")
    y_change = level_change(yields, rules.yield_sessions)
    y_points = _high_points(y_change, rules.yield_caution, rules.yield_risk)
    breakout = 0
    if len(yields) > rules.yield_breakout_sessions:
        prior_high = max(yields[-(rules.yield_breakout_sessions + 1):-1])
        moved = y_change is not None and y_change >= rules.yield_breakout_min_change
        if yields[-1] > prior_high and moved:
            breakout = 1
    parts["yield_breakout"] = breakout
    parts["rates"] = min(rules.yield_cap, y_points + breakout)
    parts["oil"] = _high_points(
        pct_change(view.closes("wti"), rules.oil_sessions), rules.oil_caution, rules.oil_risk,
    )
    btc = view.closes("btc")
    parts["btc_roc"] = _low_points(
        pct_change(btc, rules.btc_roc_sessions), rules.btc_roc_caution, rules.btc_roc_risk,
    )
    drawdown = None
    if len(btc) >= 20:
        window = btc[-rules.btc_dd_sessions:]
        peak = max(window)
        if peak > 0:
            drawdown = btc[-1] / peak - 1
    parts["btc_drawdown"] = _low_points(drawdown, rules.btc_dd_caution, rules.btc_dd_risk)
    parts["btc"] = min(rules.btc_cap, parts["btc_roc"] + parts["btc_drawdown"])
    total = parts["vix"] + parts["credit"] + parts["rates"] + parts["oil"] + parts["btc"]
    return float(total), parts


def confirmed_combo(view: AsOfView, config: Config) -> bool:
    """VIX at or above 25 and high-yield credit wider by at least 40bp over 20 sessions.

    Those two prints led the in-sample equity low. The other stress legs did not.
    """
    rules = config.regime.stress
    vix = view.closes("vix")
    if not vix or vix[-1] < rules.vix_level_caution:
        return False
    widened = level_change(view.closes("hy_oas"), rules.credit_sessions)
    return widened is not None and widened >= rules.credit_widen_caution


def _pillar_total(pillars: dict[str, dict[str, Any]], config: Config) -> tuple[list[str], float | None]:
    known = [name for name in PILLAR_ORDER if pillars[name]["color"] != "missing"]
    if pillars["rates"]["color"] == "missing" or len(known) < config.regime.min_pillars:
        return known, None
    total = sum(config.regime.weights[name] * COLOR_VALUE[pillars[name]["color"]] for name in known)
    return known, total


def _quiet_regime(pillars: dict[str, dict[str, Any]], total: float, config: Config) -> str:
    rates = pillars["rates"]["color"]
    vol = pillars["volatility"]["color"]
    if total >= config.regime.risk_on_min and rates != "red" and vol != "red":
        return "risk-on"
    return "neutral"


def _classic(pillars: dict[str, dict[str, Any]]) -> bool:
    rates = pillars["rates"]["color"]
    vol = pillars["volatility"]["color"]
    credit = pillars["credit"]["color"]
    return rates == "red" and (vol == "red" or credit == "red")


def _hysteresis(
    pillars: dict[str, dict[str, Any]],
    pillar_total: float,
    stress: float,
    prior: str | None,
    config: Config,
) -> str:
    rules = config.regime.stress
    classic = _classic(pillars)
    enter_off = stress >= rules.enter_risk_off or classic
    if prior == "risk-off":
        if stress >= rules.exit_risk_off or classic:
            return "risk-off"
        if stress >= rules.exit_caution:
            return "caution"
        return _quiet_regime(pillars, pillar_total, config)
    if prior == "caution":
        if enter_off:
            return "risk-off"
        if stress >= rules.exit_caution:
            return "caution"
        return _quiet_regime(pillars, pillar_total, config)
    if enter_off:
        return "risk-off"
    if stress >= rules.enter_caution:
        return "caution"
    return _quiet_regime(pillars, pillar_total, config)


def resolve_regime(
    pillars: dict[str, dict[str, Any]],
    pillar_total: float | None,
    stress: float,
    prior: str | None,
    config: Config,
    *,
    bottom: bool = False,
    prior_released: bool = False,
    combo: bool = False,
) -> tuple[str, bool]:
    """Return the regime and whether a buy-the-low release is holding caution off.

    v1 is the level rule. v2 is stress hysteresis. v3 leaves caution on the
    bottom signal and holds that release while residual stress is still
    elevated. v4 raises cash only when VIX and credit confirm together.
    A bottom still forces a quiet day so the book can buy.
    """
    if pillar_total is None:
        return "unknown", False
    if config.model.version == "v1":
        if pillar_total <= config.model.v1_risk_off_max or _classic(pillars):
            return "risk-off", False
        return _quiet_regime(pillars, pillar_total, config), False
    if config.model.version in {"v4", "v5", "v6"}:
        if bottom:
            return _quiet_regime(pillars, pillar_total, config), False
        if combo:
            return "risk-off", False
        if config.model.v4_caution == "light":
            raw = _hysteresis(pillars, pillar_total, stress, prior, config)
            if raw in {"caution", "risk-off"}:
                return "caution", False
            return raw, False
        return _quiet_regime(pillars, pillar_total, config), False
    acute = stress >= config.regime.stress.enter_risk_off or _classic(pillars)
    cooled = stress < config.regime.stress.exit_caution
    if config.model.version == "v3" and bottom:
        return _quiet_regime(pillars, pillar_total, config), True
    if config.model.version == "v3" and prior_released and not acute and not cooled:
        return _quiet_regime(pillars, pillar_total, config), True
    return _hysteresis(pillars, pillar_total, stress, prior, config), False


def _hold_state(
    config: Config,
    bottom: bool,
    regime: str,
    prior_hold: bool,
    prior_quiet: bool,
) -> tuple[bool, bool]:
    """Hold redeployed shares until the next warning after a quiet day.

    The warning that is already on at the bottom does not count. Quiet up-days
    do not release the hold.
    """
    if config.model.version not in {"v4", "v5", "v6"}:
        return False, False
    if bottom:
        return True, False
    warning = regime in {"caution", "risk-off"}
    if prior_hold and warning and prior_quiet:
        return False, False
    if prior_hold and not warning and regime != "unknown":
        return True, True
    return prior_hold, prior_quiet


def score_asof(
    panel: SeriesPanel,
    day: date,
    config: Config,
    *,
    prior_regime: str | None = None,
    prior_released: bool = False,
    prior_hold: bool = False,
    prior_quiet: bool = False,
) -> dict[str, Any]:
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
    _known, total = _pillar_total(pillars, config)
    stress, parts = stress_score(view, config)
    bottom = is_bottom(view, config)
    combo = confirmed_combo(view, config)
    regime, released = resolve_regime(
        pillars, total, stress, prior_regime, config,
        bottom=bottom, prior_released=prior_released, combo=combo,
    )
    hold, quiet = _hold_state(config, bottom, regime, prior_hold, prior_quiet)
    today = events_on(day, config)
    ahead = upcoming(day, config, config.events.horizon_days)
    rules = config.regime.stress
    return {
        "date": day.isoformat(),
        "regime": regime,
        "score": total,
        "stress": stress,
        "stress_parts": parts,
        "bottom": bottom,
        "released": released,
        "combo": combo,
        "redeploy_hold": hold,
        "redeploy_quiet": quiet,
        "prior_regime": prior_regime,
        "pillars": pillars,
        "oil_shock": shock,
        "events_today": today,
        "events_upcoming": ahead,
        "regime_rule": (
            "Risk-on when the weighted pillar total is at least "
            f"{config.regime.risk_on_min} and neither rates nor volatility is red. "
            f"A stress score of rate-of-change points (VIX jump, credit widening, 30y breakout, "
            f"oil shock, BTC drawdown) enters caution at {rules.enter_caution:g} and risk-off at "
            f"{rules.enter_risk_off:g}. It leaves risk-off below {rules.exit_risk_off:g} and caution "
            f"below {rules.exit_caution:g}. Red rates plus red volatility or red credit is still an "
            "entry backstop. In v3 a buy-the-low day leaves caution immediately and holds that "
            "release until the stress score cools below the caution exit or a fresh acute spike hits. "
            "In v4 the large cash raise is only VIX at or above "
            f"{rules.vix_level_caution:g} plus credit wider by {rules.credit_widen_caution:.2f}. "
            "Redeployed shares stay on until the next warning after a quiet day. "
            "Unknown when rates are missing or fewer than "
            f"{config.regime.min_pillars} pillars have data."
        ),
    }


def score_path(panel: SeriesPanel, days: list[date], config: Config) -> list[dict[str, Any]]:
    """Walk sessions in order so hysteresis can see yesterday and not tomorrow."""
    prior: str | None = None
    released = False
    hold = False
    quiet = False
    rows = []
    for day in days:
        row = score_asof(
            panel, day, config,
            prior_regime=prior, prior_released=released, prior_hold=hold, prior_quiet=quiet,
        )
        rows.append(row)
        if row["regime"] != "unknown":
            prior = row["regime"]
        released = bool(row["released"])
        hold = bool(row["redeploy_hold"])
        quiet = bool(row["redeploy_quiet"])
    return rows


def scoring_days(panel: SeriesPanel, config: Config) -> list[date]:
    start = min(config.window.warmup_start, config.window.start)
    return [day for day in panel.dates("spy") if start <= day <= config.window.end]


def score_on(path: list[dict[str, Any]], day: date) -> dict[str, Any] | None:
    """Latest scored session on or before `day`."""
    chosen = None
    for row in path:
        if date.fromisoformat(row["date"]) <= day:
            chosen = row
        else:
            break
    return chosen
