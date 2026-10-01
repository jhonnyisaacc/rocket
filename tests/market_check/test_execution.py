"""Execution realism: decisions on day T must fill at the next session, never at T's close."""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from rocket.market_check.config import load_config
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.portfolio import simulate_portfolio
from rocket.market_check.redeploy import is_bottom

CFG = load_config()


def _weekdays(start: date, count: int) -> list[date]:
    rows = []
    cursor = start
    while len(rows) < count:
        if cursor.weekday() < 5:
            rows.append(cursor)
        cursor += timedelta(days=1)
    return rows


def _scenario() -> tuple[SeriesPanel, list[date]]:
    """A stress spike that fades while the index is still deeply drawn down.

    Day 68 is the first bottom signal; day 69 repeats it with names bouncing,
    so redeploy buys are decided on day 69. Day 70 gaps names +10% so a
    same-close fill and a next-session fill cannot agree.
    """
    days = _weekdays(date(2024, 4, 1), 120)
    series: dict[str, dict[str, float]] = {}
    base_names = [
        "yield_2y",
        "yield_10y",
        "yield_30y",
        "fed_funds",
        "wti",
        "brent",
        "vix",
        "hy_oas",
        "tlt",
        "dollar",
        "gold",
        "btc",
        "dvol",
        "funding_daily",
        "spy",
        "qqq",
        *CFG.portfolio.universe,
    ]
    levels = {
        "yield_2y": 3.4,
        "yield_10y": 3.5,
        "yield_30y": 4.0,
        "fed_funds": 3.5,
        "wti": 70.0,
        "brent": 74.0,
        "vix": 14.0,
        "hy_oas": 3.0,
        "tlt": 90.0,
        "dollar": 102.0,
        "gold": 2300.0,
        "btc": 100.0,
        "dvol": 50.0,
        "funding_daily": 0.00001,
    }
    for name in base_names:
        series[name] = {}
        for index, day in enumerate(days):
            base = levels.get(name, 100.0)
            series[name][day.isoformat()] = base * (1 + index * 0.0002)
    spy = [100.0] * 60 + [97.0, 94.0, 91.0, 88.0, 86.0] + [86.0] * 55
    vix = (
        [14.0] * 60 + [22.0, 30.0, 40.0, 48.0, 55.0] + [50.0, 45.0, 40.0, 35.0, 30.0] + [30.0] * 50
    )
    hy = [3.0] * 60 + [3.1, 3.2, 3.4, 3.6, 3.8] + [3.8] * 55
    names_path = (
        [100.0] * 60
        + [97.0, 94.0, 91.0, 88.0, 85.0]
        + [85.0, 85.0, 85.85, 86.7, 87.6]
        + [87.6 * 1.10] * 50
    )
    assert len(spy) == len(days) == 120
    for index, day in enumerate(days):
        key = day.isoformat()
        series["spy"][key] = spy[index]
        series["vix"][key] = vix[index]
        series["hy_oas"][key] = hy[index]
        for name in CFG.portfolio.universe:
            series[name][key] = names_path[index]
    return SeriesPanel(series), days


def _config(days: list[date]):
    return replace(
        CFG,
        model=replace(CFG.model, version="v4"),
        window=replace(
            CFG.window,
            start=days[0],
            end=days[-1],
            oos_start=days[60],
            ondo_live=days[-1],
        ),
    )


def _spy_sessions(panel: SeriesPanel, config) -> list[date]:
    return [day for day in panel.dates("spy") if config.window.start <= day <= config.window.end]


def test_bottom_signal_exists_before_any_redeploy_buy():
    panel, days = _scenario()
    config = _config(days)
    bottoms = [
        day
        for day in _spy_sessions(panel, config)
        if is_bottom(panel.asof(day, config.lags), config)
    ]
    assert bottoms, "scenario must contain at least one bottom signal"


def test_redeploy_fills_at_the_next_session_not_the_signal_close():
    panel, days = _scenario()
    config = _config(days)
    slip = config.costs.equity_slippage_bps / 10_000
    sessions = _spy_sessions(panel, config)
    bottoms = {day for day in sessions if is_bottom(panel.asof(day, config.lags), config)}
    assert bottoms, "scenario must contain at least one bottom signal"
    result = simulate_portfolio(panel, config)
    buys = [t for t in result["trades"] if t["reason"].startswith("redeploy")]
    assert buys, "scenario must produce at least one redeploy buy"
    for trade in buys:
        decided = date.fromisoformat(trade["decided"])
        filled = date.fromisoformat(trade["date"])
        assert decided in bottoms, "redeploy must be decided on a bottom signal day"
        assert filled == sessions[sessions.index(decided) + 1], (
            "fill must print on the next session after the decision"
        )
        next_price = panel.asof(filled, config.lags).value(trade["ticker"])
        signal_price = panel.asof(decided, config.lags).value(trade["ticker"])
        assert next_price != pytest.approx(signal_price), "scenario gap must separate the two fills"
        assert trade["price"] == pytest.approx(next_price * (1 + slip)), (
            "buy fill must use the next session price plus slippage"
        )


def test_fill_day_shock_changes_prices_not_decisions():
    panel, days = _scenario()
    config = _config(days)
    base = simulate_portfolio(panel, config)
    base_buys = [t for t in base["trades"] if t["reason"].startswith("redeploy")]
    assert base_buys
    fill_day = date.fromisoformat(base_buys[0]["date"]).isoformat()
    shocked = panel.copy_with(
        {
            name: {
                fill_day: panel.asof(
                    date.fromisoformat(fill_day),
                    config.lags,
                ).value(name)
                * 1.5
            }
            for name in CFG.portfolio.universe
        }
    )
    moved = simulate_portfolio(shocked, config)
    moved_buys = [t for t in moved["trades"] if t["reason"].startswith("redeploy")]
    before = [t for t in base_buys if t["decided"] < fill_day]
    moved_before = [t for t in moved_buys if t["decided"] < fill_day]
    assert [(t["decided"], t["ticker"], t["side"], t["reason"]) for t in moved_before] == [
        (t["decided"], t["ticker"], t["side"], t["reason"]) for t in before
    ], "a fill-day shock must not rewrite earlier decisions"
    filling = [t for t in base_buys if t["date"] == fill_day]
    moved_filling = [t for t in moved_buys if t["date"] == fill_day]
    assert filling and moved_filling, "shock day must stay a fill day in both runs"
    assert any(
        new["price"] != pytest.approx(old["price"])
        for new, old in zip(moved_filling, filling)
        if (new["decided"], new["ticker"]) == (old["decided"], old["ticker"])
    ), "a fill-day shock must move fill prices"


def _btc_panel(days: list[date], prices: list[float]) -> SeriesPanel:
    from rocket.market_check.config import load_config as _load

    cfg = _load()
    series: dict[str, dict[str, float]] = {}
    names = [
        "yield_2y",
        "yield_10y",
        "yield_30y",
        "fed_funds",
        "wti",
        "brent",
        "vix",
        "hy_oas",
        "tlt",
        "dollar",
        "gold",
        "btc",
        "dvol",
        "funding_daily",
        "spy",
        "qqq",
        *cfg.portfolio.universe,
    ]
    for name in names:
        series[name] = {day.isoformat(): 100.0 for day in days}
        if name == "vix":
            series[name] = {day.isoformat(): 14.0 for day in days}
        if name == "hy_oas":
            series[name] = {day.isoformat(): 3.0 for day in days}
    for day, price in zip(days, prices):
        series["btc"][day.isoformat()] = price
    return SeriesPanel(series)


def test_v5_long_takes_profit_and_cuts_loss():
    from rocket.market_check.derivatives import _apply_v5_exits

    days = _weekdays(date(2025, 3, 3), 40)
    # Entry fill 100, then +35% by day 10: the target (20%) must fire first.
    winner = [100.0] * 5 + [100.0 + 4 * i for i in range(35)]
    panel = _btc_panel(days, winner)
    config = replace(
        CFG,
        model=replace(CFG.model, version="v5"),
        window=replace(
            CFG.window, start=days[0], end=days[-1], oos_start=days[-1], ondo_live=days[-1]
        ),
        derivatives=replace(CFG.derivatives, stop=0.15, profit_take=0.20),
    )
    entry, month_end = days[5], days[-1]
    legs = _apply_v5_exits(panel, config, days, [(entry, month_end, False)])
    assert len(legs) == 1
    out_entry, out_exit, stopped = legs[0]
    assert out_entry == entry
    assert not stopped
    assert days.index(out_exit) <= 15, "profit-take must fire near the +20% cross"
    # Loser: -20% drift hits the 15% stop.
    loser = [100.0] * 5 + [100.0 - 0.7 * i for i in range(35)]
    panel = _btc_panel(days, loser)
    legs = _apply_v5_exits(panel, config, days, [(entry, month_end, False)])
    assert len(legs) == 1
    _entry, exit_day, stopped = legs[0]
    assert stopped, "a failed bounce must stop out"
    assert days.index(exit_day) <= 30
    # Flat market: the warning exit stands.
    flat = [100.0] * 40
    panel = _btc_panel(days, flat)
    legs = _apply_v5_exits(panel, config, days, [(entry, month_end, False)])
    assert legs == [(entry, month_end, False)]


def test_later_shock_leaves_earlier_trades_put():
    panel, days = _scenario()
    config = _config(days)
    base = simulate_portfolio(panel, config)
    assert base["trades"]
    last_trade_day = max(date.fromisoformat(t["date"]) for t in base["trades"])
    sessions = _spy_sessions(panel, config)
    later = [d for d in sessions if d > last_trade_day]
    assert later, "scenario needs sessions after the last trade"
    shock_key = later[len(later) // 2].isoformat()
    shocked = panel.copy_with({name: {shock_key: 1e6} for name in ("spy", *CFG.portfolio.universe)})
    moved = simulate_portfolio(shocked, config)
    key = lambda t: (t["date"], t["decided"], t["ticker"], t["side"], t["reason"])
    before = [key(t) for t in base["trades"] if t["date"] < shock_key]
    moved_before = [key(t) for t in moved["trades"] if t["date"] < shock_key]
    assert before, "scenario needs trades before the shock day"
    assert moved_before == before
