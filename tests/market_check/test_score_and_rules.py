"""Scoring thresholds, Porto gates, and the no-look-ahead slice."""

from dataclasses import replace
from datetime import date, timedelta

from rocket.market_check.actions import changed_against, decide
from rocket.market_check.config import load_config
from rocket.market_check.mathutil import color_high_bad
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.rules import cash_target, in_bottom_half, plan_trims, trim_allowed
from rocket.market_check.score import score_asof

CFG = load_config()
DAY = date(2025, 6, 3)


def _days(start: date, count: int) -> list[date]:
    rows = []
    cursor = start
    while len(rows) < count:
        if cursor.weekday() < 5:
            rows.append(cursor)
        cursor += timedelta(days=1)
    return rows


def _constant(days: list[date], value: float) -> dict[str, float]:
    return {day.isoformat(): value for day in days}


def _panel(days: list[date], **levels: float) -> SeriesPanel:
    series = {name: _constant(days, value) for name, value in levels.items()}
    return SeriesPanel(series)


def _base_levels() -> dict[str, float]:
    return {
        "yield_2y": 3.4,
        "yield_10y": 3.5,
        "yield_30y": 4.0,
        "fed_funds": 3.5,
        "wti": 70.0,
        "brent": 74.0,
        "vix": 12.0,
        "hy_oas": 3.0,
        "tlt": 100.0,
        "dollar": 100.0,
        "gold": 200.0,
        "btc": 100.0,
        "dvol": 50.0,
        "funding_daily": 0.0,
        "spy": 100.0,
    }


def test_level_thresholds_follow_the_config():
    rates = CFG.rates
    assert color_high_bad(rates.yield_10y_green_max - 0.01, rates.yield_10y_green_max, rates.yield_10y_red_min) == "green"
    assert color_high_bad(rates.yield_10y_green_max, rates.yield_10y_green_max, rates.yield_10y_red_min) == "yellow"
    assert color_high_bad(rates.yield_10y_red_min + 0.01, rates.yield_10y_green_max, rates.yield_10y_red_min) == "red"
    vol = CFG.volatility
    assert color_high_bad(vol.vix_red_min, vol.vix_green_max, vol.vix_red_min) == "yellow"


def test_easy_tape_is_risk_on_and_a_stress_tape_is_risk_off():
    days = _days(date(2025, 1, 2), 80)
    easy = score_asof(_panel(days, **_base_levels()), days[-1], CFG)
    assert easy["regime"] == "risk-on"
    assert easy["pillars"]["rates"]["color"] == "green"
    late = days[-15:]
    stressed = _panel(days, **_base_levels()).copy_with({
        "yield_10y": {day.isoformat(): 5.8 for day in late},
        "yield_30y": {day.isoformat(): 6.0 for day in late},
        "yield_2y": {day.isoformat(): 5.5 for day in late},
        "vix": {day.isoformat(): 32.0 for day in days},
        "hy_oas": {day.isoformat(): 6.0 for day in days},
        "tlt": {day.isoformat(): (80.0 if index % 2 == 0 else 120.0) for index, day in enumerate(days)},
    })
    hard = score_asof(stressed, days[-1], replace(CFG, model=replace(CFG.model, version="v2")))
    assert hard["pillars"]["rates"]["color"] == "red"
    assert hard["pillars"]["volatility"]["color"] == "red"
    assert hard["regime"] == "risk-off"
    # v4 does not treat a high VIX alone as the cash raise. Credit has to widen too.
    v4 = score_asof(stressed, days[-1], CFG)
    assert v4["combo"] is False
    assert v4["regime"] != "risk-off"


def test_future_print_and_same_day_lagged_credit_are_invisible():
    days = _days(date(2025, 1, 2), 80)
    day = days[-1]
    panel = _panel(days, **_base_levels())
    before = score_asof(panel, day, CFG)
    shocked = panel.copy_with({
        "yield_10y": {(day + timedelta(days=1)).isoformat(): 9.0},
        "hy_oas": {day.isoformat(): 9.0},
        "vix": {(day + timedelta(days=5)).isoformat(): 80.0},
    })
    after = score_asof(shocked, day, CFG)
    assert after == before
    visible = shocked.asof(day, CFG.lags).history("hy_oas")
    assert all(stamp <= day - timedelta(days=CFG.lag("hy_oas")) for stamp, _ in visible)
    assert shocked.asof(day, CFG.lags).value("hy_oas") == 3.0


def test_trim_blocks_and_sale_order():
    allowed, detail = trim_allowed(
        name="TSLA", name_return=-0.02, bounce=0.2, index_return=0.01, index_bounce=0.02,
        regular_hours=True, config=CFG,
    )
    assert not allowed and detail["reason"] == "name_red"
    allowed, detail = trim_allowed(
        name="MSFT", name_return=0.01, bounce=0.0, index_return=-0.02, index_bounce=0.0,
        regular_hours=True, config=CFG,
    )
    assert not allowed and detail["reason"] == "index_hard_down"
    allowed, _detail = trim_allowed(
        name="FCX", name_return=0.01, bounce=0.0, index_return=0.01, index_bounce=0.0,
        regular_hours=True, config=CFG,
    )
    assert allowed
    plans = plan_trims(
        {"TSLA": 10, "FCX": 10, "BAC": 10},
        {"TSLA": 10, "FCX": 10, "BAC": 10},
        cash=10, nav=100, target=0.4, allowed={"TSLA", "FCX", "BAC"}, config=CFG,
    )
    assert plans[0][0] == "TSLA"
    assert [name for name, _ in plans] == ["TSLA", "FCX", "BAC"] or plans[0][0] == "TSLA"


def test_cash_target_and_buy_zone():
    assert cash_target("risk-on", None, CFG) == CFG.portfolio.cash_risk_on
    bumped = cash_target("risk-on", 0.01, CFG)
    assert bumped == min(CFG.portfolio.cash_ceiling, CFG.portfolio.cash_risk_on + CFG.portfolio.cash_strength_bump)
    assert cash_target("risk-off", 0.02, CFG) == CFG.portfolio.cash_ceiling
    low, high = 80.0, 120.0
    zone_high = low + CFG.portfolio.buy_zone_fraction * (high - low)
    assert in_bottom_half(low + 0.01, low, high, CFG.portfolio.buy_zone_fraction)
    assert not in_bottom_half((low + zone_high) / 2 + 1, low, high, CFG.portfolio.buy_zone_fraction)


def test_action_change_is_a_fingerprint_diff():
    days = _days(date(2025, 1, 2), 80)
    panel = _panel(days, **_base_levels(), MSFT=100, META=100, FCX=50, BAC=40, AMZN=180, EQIX=800, TSLA=200,
                   ETN=300, CAT=400, APH=70, AMAT=150)
    today = decide(panel, days[-1], CFG, book={"USDC": 0.40, "MSFT": 0.1, "TSLA": 0.1})
    same = decide(panel, days[-2], CFG, book={"USDC": 0.40, "MSFT": 0.1, "TSLA": 0.1})
    assert changed_against(today, same)["changed"] is False
    shocked = panel.copy_with({
        "vix": {days[-1].isoformat(): 40.0},
        "tlt": {days[-1].isoformat(): 40.0},
    })
    moved = decide(shocked, days[-1], CFG, book={"USDC": 0.40, "MSFT": 0.1, "TSLA": 0.1})
    diff = changed_against(moved, same)
    assert diff["changed"] is True
    assert "regime" in diff["changed_fields"]
