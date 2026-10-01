"""Backtest accounting, option marks, and the guarantee that later data cannot change an earlier day."""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from rocket.market_check.bs import bs_put
from rocket.market_check.config import load_config
from rocket.market_check.derivatives import simulate_derivatives
from rocket.market_check.metrics import max_drawdown, performance
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.portfolio import simulate_portfolio
from rocket.market_check.score import score_asof
from rocket.market_check.scorecard import pending_due

CFG = load_config()


def _weekdays(start: date, count: int) -> list[date]:
    rows = []
    cursor = start
    while len(rows) < count:
        if cursor.weekday() < 5:
            rows.append(cursor)
        cursor += timedelta(days=1)
    return rows


def _panel(days: list[date]) -> SeriesPanel:
    series: dict[str, dict[str, float]] = {}
    names = [
        "yield_2y", "yield_10y", "yield_30y", "fed_funds", "wti", "brent", "vix", "hy_oas",
        "tlt", "dollar", "gold", "btc", "dvol", "funding_daily", "spy", "qqq",
        *CFG.portfolio.universe,
    ]
    levels = {
        "yield_2y": 3.4, "yield_10y": 3.5, "yield_30y": 4.0, "fed_funds": 3.5,
        "wti": 70.0, "brent": 74.0, "vix": 12.0, "hy_oas": 3.0, "tlt": 90.0,
        "dollar": 102.0, "gold": 2300.0, "btc": 100.0, "dvol": 50.0, "funding_daily": 0.00001,
    }
    for name in names:
        series[name] = {}
        for index, day in enumerate(days):
            base = levels.get(name, 100.0 + (index % 7))
            series[name][day.isoformat()] = base * (1 + index * 0.0005)
    return SeriesPanel(series)


def _window(start: date, end: date, oos: date):
    return replace(
        CFG,
        window=replace(CFG.window, start=start, end=end, oos_start=oos, ondo_live=end),
    )


def test_put_price_matches_the_zero_rate_reference():
    # r=0, K=S, one year, 20 vol. Put = 100 * (2*N(0.1) - 1).
    price = bs_put(100, 100, 1.0, 0.2, 0.0)
    assert abs(price - 7.965567) < 1e-3


def test_drawdown_and_flat_sharpe():
    days = [date(2024, 1, 2) + timedelta(days=index) for index in range(4)]
    assert max_drawdown([100, 80, 90, 70]) == pytest.approx(-0.3)
    stats = performance(days, [1, 1, 1, 1])
    assert stats["cagr"] == 0
    assert stats["volatility"] == 0
    assert stats["sharpe"] is None


def test_earlier_session_does_not_see_a_later_shock():
    days = _weekdays(date(2024, 6, 3), 90)
    panel = _panel(days)
    config = _window(days[10], days[70], days[40])
    regimes = [score_asof(panel, day, config)["regime"] for day in days[10:40]]
    shocked = panel.copy_with({
        "spy": {days[50].isoformat(): 1e9},
        "yield_10y": {days[55].isoformat(): 12.0},
        "btc": {days[60].isoformat(): 1.0},
    })
    again = [score_asof(shocked, day, config)["regime"] for day in days[10:40]]
    assert regimes == again
    changed = score_asof(shocked, days[55], config)
    untouched = score_asof(shocked, days[54], config)
    original = score_asof(panel, days[54], config)
    assert untouched == original
    level = next(sub for sub in changed["pillars"]["rates"]["subs"] if sub["name"] == "yield_10y_level")
    assert level["color"] == "red"
    assert level["value"] == 12.0


def test_portfolio_trades_before_a_shock_stay_put():
    days = _weekdays(date(2024, 6, 3), 90)
    panel = _panel(days)
    config = _window(days[5], days[80], days[50])
    base = simulate_portfolio(panel, config)
    shock_day = days[60]
    shocked = panel.copy_with({name: {shock_day.isoformat(): 1e6} for name in ("spy", *config.portfolio.universe)})
    moved = simulate_portfolio(shocked, config)
    before = [trade for trade in base["trades"] if trade["date"] < shock_day.isoformat()]
    after = [trade for trade in moved["trades"] if trade["date"] < shock_day.isoformat()]
    assert before == after
    assert before
    assert all(trade["side"] != "short" for trade in base["trades"])
    assert min(row["nav"] for row in base["nav"]) > 0


def test_short_perp_stops_out_and_does_not_use_the_next_month():
    days = _weekdays(date(2024, 10, 1), 160)
    panel = _panel(days)
    entry = date(2025, 3, 3)
    spike = date(2025, 3, 7)
    btc = {}
    yields_10, yields_30, yields_2, vix, hy = {}, {}, {}, {}, {}
    for day in days:
        btc[day.isoformat()] = 100.0 if day < entry else (70.0 if day < spike else 95.0)
        stressed = day >= date(2025, 2, 3)
        yields_10[day.isoformat()] = 6.0 if stressed else 3.8
        yields_30[day.isoformat()] = 6.4 if stressed else 4.0
        yields_2[day.isoformat()] = 6.6 if stressed else 3.6
        vix[day.isoformat()] = 36.0 if stressed else 14.0
        hy[day.isoformat()] = 6.5 if stressed else 3.0
    panel = panel.copy_with({
        "btc": btc, "yield_10y": yields_10, "yield_30y": yields_30, "yield_2y": yields_2,
        "vix": vix, "hy_oas": hy,
        "tlt": {day.isoformat(): (70.0 if index % 2 == 0 else 110.0) for index, day in enumerate(days)},
    })
    # v3 does not short. This guard covers the monthly engine, which v1 and v2 still use.
    config = replace(_window(entry, date(2025, 3, 31), entry), model=replace(CFG.model, version="v2"))
    result = simulate_derivatives(panel, config)
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["position"] == "short"
    assert row["stopped"] is True
    assert row["success"] is False
    assert abs(row["pnl"]) < 1
    assert row["exit_date"] == spike.isoformat()
    later = panel.copy_with({"btc": {(date(2025, 4, 15)).isoformat(): 1.0}})
    assert simulate_derivatives(later, config)["rows"] == result["rows"]


def test_pending_scorecard_rows_inside_the_horizon():
    rows = [
        {"id": "1", "claim": "soon", "status": "pending", "deadline_check_date": "2026-10-09", "notes": "", "testable_metric": ""},
        {"id": "2", "claim": "later", "status": "pending", "deadline_check_date": "2027-03-31", "notes": "", "testable_metric": ""},
        {"id": "3", "claim": "done", "status": "wrong", "deadline_check_date": "2026-10-09", "notes": "", "testable_metric": ""},
    ]
    due = pending_due(rows, date(2026, 10, 1), within_days=21)
    assert [row["id"] for row in due] == ["1"]
