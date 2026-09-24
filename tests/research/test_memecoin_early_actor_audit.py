from __future__ import annotations

import json

from scripts.research.memecoin_early_actor_audit import select


def test_selection_uses_receive_window_and_excludes_multi_event_transactions(tmp_path):
    fast = [{"mint": mint, "signature": f"create-{mint}", "split": "development",
             "flow_score": score, "create_received_at": "2026-09-24T00:00:00+00:00"}
            for mint, score in (("top", 3), ("rest1", 2), ("rest2", 1), ("rest3", 0))]
    (tmp_path / "mc010-fast-flow-rows.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in fast))
    trades = [
        {"signature": "early-top", "mint": "top", "available_at": "2026-09-24T00:00:05+00:00",
         "is_buy": True},
        {"signature": "late-top", "mint": "top", "available_at": "2026-09-24T00:00:05.001+00:00",
         "is_buy": True},
        {"signature": "early-rest", "mint": "rest1", "available_at": "2026-09-24T00:00:01+00:00",
         "is_buy": False},
        {"signature": "multi", "mint": "top", "available_at": "2026-09-24T00:00:01+00:00",
         "is_buy": True},
        {"signature": "multi", "mint": "top", "available_at": "2026-09-24T00:00:06+00:00",
         "is_buy": True},
    ]
    for row in trades:
        row.update(event_type="TradeEvent", slot=1, user="wallet", token_amount=10,
                   source_hash="f" * 64)
    (tmp_path / "observations.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in trades))
    result = select(tmp_path)
    assert result["early_unique_trade_signatures"] == 3
    assert result["excluded_multi_trade_signatures"] == 1
    assert result["population"] == {"top_buy": 1, "rest_buy": 0,
                                    "top_sell": 0, "rest_sell": 1}
    assert {row["signature"] for row in result["selected"]} == {"early-top", "early-rest"}
