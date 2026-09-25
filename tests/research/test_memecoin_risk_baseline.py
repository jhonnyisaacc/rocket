from __future__ import annotations

import json

from scripts.research.memecoin_risk_baseline import risk_result


def test_exit_failure_is_kept_as_risk_and_missing_entry_stays_unknown(tmp_path):
    baseline = {
        "feature_checkpoint_seconds": 5,
        "entry_seconds": 7,
        "exit_seconds": 67,
        "size_lamports": 10_000_000,
        "slippage_bps_each_leg": 200,
        "network_cost_lamports_each_leg": 155_000,
    }
    (tmp_path / "mc002-result.json").write_text(json.dumps(baseline))
    rows = [
        {"status": "QUOTED", "reason": None, "split": "development", "score": 0.8,
         "signature": "a", "outcome": {"net_quote_proxy_return": 0.1}},
        {"status": "CENSORED", "reason": "EXIT_UNAVAILABLE:insufficient exit liquidity",
         "split": "development", "score": 0.2, "signature": "b",
         "entry_quote": {"cash": 10_000_000}},
        {"status": "CENSORED", "reason": "NO_AS_OF_ENTRY_FEE_STATE",
         "split": "development", "score": 0.1, "signature": "c"},
    ]
    (tmp_path / "universe.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))
    result = risk_result(tmp_path)
    assert result["development"]["all"]["entry_known"] == 2
    assert result["development"]["all"]["exit_unavailable"] == 1
    assert result["development"]["all"]["unknown"] == 1
    assert result["development"]["all"]["stress_mean"] < -0.4
    assert result["development"]["top_quartile"]["stress_mean"] == 0.1
