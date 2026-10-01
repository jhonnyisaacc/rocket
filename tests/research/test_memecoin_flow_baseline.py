from __future__ import annotations

import pytest

from scripts.research.memecoin_flow_baseline import scenario_return, score_snapshot


def test_flow_score_uses_only_frozen_early_count_features():
    snapshot = {"schema": "rocket.memecoin.pit-snapshot.v2",
                "features": {"observed_buys_5s": 7, "observed_sells_5s": 2,
                             "curve_progress_5s": 0.9}}
    assert score_snapshot(snapshot) == 5
    snapshot["features"]["observed_buys_5s"] = -1
    with pytest.raises(ValueError):
        score_snapshot(snapshot)


def test_network_scenario_charges_both_legs_and_zero_recovery():
    quoted = {"status": "QUOTED", "outcome": {
        "entry_quote": {"cash": 10_000_000}, "stressed_exit_cash_lamports": 11_000_000}}
    unavailable = {"status": "CENSORED", "reason": "EXIT_UNAVAILABLE:insufficient exit liquidity",
                   "entry_quote": {"cash": 10_000_000}}
    assert scenario_return(quoted, 1_000_000) == -1_000_000 / 11_000_000
    assert scenario_return(unavailable, 1_000_000) == -12_000_000 / 11_000_000
