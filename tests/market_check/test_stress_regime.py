"""Stress-score hysteresis, and recognition of a sale the simulator already made."""

from dataclasses import replace
from datetime import date, timedelta

from rocket.market_check.config import load_config
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.portfolio import compare_trade_log
from rocket.market_check.score import _hold_state, score_path

CFG = load_config()
V2 = replace(CFG, model=replace(CFG.model, version="v2"))


def _days(start: date, count: int) -> list[date]:
    rows = []
    cursor = start
    while len(rows) < count:
        if cursor.weekday() < 5:
            rows.append(cursor)
        cursor += timedelta(days=1)
    return rows


def _panel(days: list[date]) -> SeriesPanel:
    series = {}
    levels = {
        "yield_2y": 3.4, "yield_10y": 3.5, "yield_30y": 4.0, "fed_funds": 3.5,
        "wti": 70.0, "brent": 74.0, "vix": 12.0, "hy_oas": 3.0, "tlt": 100.0,
        "dollar": 100.0, "gold": 200.0, "btc": 100.0, "dvol": 50.0,
        "funding_daily": 0.0, "spy": 100.0,
    }
    for name, value in levels.items():
        series[name] = {day.isoformat(): value for day in days}
    return SeriesPanel(series)


def test_a_spike_enters_risk_off_and_hysteresis_steps_down_through_caution():
    days = _days(date(2025, 1, 2), 40)
    panel = _panel(days)
    shock = days[-8]
    calm_again = days[-1]
    panel = panel.copy_with({
        "vix": {shock.isoformat(): 50.0, **{day.isoformat(): 26.0 for day in days[-7:-1]}},
        "wti": {shock.isoformat(): 80.0},
    })
    path = {row["date"]: row for row in score_path(panel, days, V2)}
    assert path[shock.isoformat()]["regime"] == "risk-off"
    assert path[shock.isoformat()]["stress"] >= CFG.regime.stress.enter_risk_off
    # The spike is still inside the 5-session VIX window here, so the book stays risk-off.
    assert path[days[-4].isoformat()]["regime"] == "risk-off"
    assert path[calm_again.isoformat()]["regime"] in {"caution", "risk-on", "neutral"}
    assert path[calm_again.isoformat()]["regime"] != "risk-off"


def test_a_later_shock_does_not_rewrite_an_earlier_regime():
    days = _days(date(2025, 1, 2), 40)
    panel = _panel(days)
    before = [row["regime"] for row in score_path(panel, days[:20], V2)]
    shocked = panel.copy_with({"vix": {days[-1].isoformat(): 80.0}, "wti": {days[-1].isoformat(): 120.0}})
    after = [row["regime"] for row in score_path(shocked, days[:20], V2)]
    assert before == after


def test_logged_sale_is_recognized_when_the_simulator_already_exited():
    logged = [{"date": date(2026, 9, 23), "ticker": "TSLA", "side": "sell", "note": "sold all"}]
    simulated = [
        {"date": "2024-10-01", "ticker": "TSLA", "side": "buy", "shares": 1.0},
        {"date": "2025-03-12", "ticker": "TSLA", "side": "sell", "shares": 1.0},
    ]
    row = compare_trade_log(logged, simulated)[0]
    assert row["matched"] is False
    assert row["recognized"] is True
    assert row["status"] == "already_exited"
    assert row["last_simulated"] == "2025-03-12"
    assert row["days_apart"] > 5


def test_v4_hold_survives_the_warning_already_on_and_releases_on_the_next_one():
    hold, quiet = _hold_state(CFG, True, "neutral", False, False)
    assert (hold, quiet) == (True, False)
    hold, quiet = _hold_state(CFG, False, "risk-off", hold, quiet)
    assert (hold, quiet) == (True, False)
    hold, quiet = _hold_state(CFG, False, "neutral", hold, quiet)
    assert (hold, quiet) == (True, True)
    hold, quiet = _hold_state(CFG, False, "risk-on", hold, quiet)
    assert hold is True
    hold, quiet = _hold_state(CFG, False, "risk-off", hold, quiet)
    assert (hold, quiet) == (False, False)
