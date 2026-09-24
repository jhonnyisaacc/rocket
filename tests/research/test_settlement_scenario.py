"""A forced settlement closes inventory before the next rejected entry order."""

import pytest

from research.futures import settlement_scenario as scenario
from research.futures.fut001 import DAY_MS, START_MS


def test_intraday_settlement_and_next_day_rejected_order(monkeypatch):
    monkeypatch.setattr(scenario, "DISCOVERY_END_MS", START_MS + 2 * DAY_MS)
    signals = {
        START_MS: {"XUSDT": {"multi": 1, "single": 1, "vol": 1,
                              "return": None, "funding": 0.01, "unresolved": []}},
        START_MS + DAY_MS: {"XUSDT": {"multi": 1, "single": 1, "vol": 1,
                                       "return": None, "funding": None,
                                       "unresolved": ["missing_or_inactive_fill"]}},
    }
    fills = {START_MS: {"XUSDT": True}, START_MS + DAY_MS: {"XUSDT": False}}
    events = {(START_MS, "XUSDT"): {"open": 100, "low": 90, "mid": 95,
                                     "high": 110, "funding_official": 0.01,
                                     "funding_low": 0.01, "funding_high": 0.01,
                                     "status": "PROVISIONAL"}}
    result = scenario.score_discovery(signals, fills, events, component="multi",
                                      bps=20, scenario="mid")
    assert result["unresolved_exposures"] == []
    assert result["forced_settlements"] == 1
    assert result["rejected_orders"] == 1
    # First day: 5% weight times -5% move, 1% funding, then full entry/exit cost.
    assert result["discovery"]["mean_daily_net"] == pytest.approx(
        (0.05 * -0.05 - 0.05 * 0.01 - 0.1 * 20 / 20_000) / 2)


def test_adverse_price_depends_on_position_side():
    event = {"open": 100, "low": 90, "mid": 100, "high": 110}
    assert scenario.scenario_return(event, 0.05, "adverse") == pytest.approx(-0.1)
    assert scenario.scenario_return(event, -0.05, "adverse") == pytest.approx(0.1)
    assert scenario.scenario_return(event, 0.05, "favorable_stress") == pytest.approx(0.155)


def test_late_funding_is_bounded_against_position_side():
    event = {"funding_official": 0.01, "funding_low": 0.01, "funding_high": 0.04}
    assert scenario.scenario_funding(event, 0.05, "adverse") == 0.04
    assert scenario.scenario_funding(event, -0.05, "adverse") == 0.01
