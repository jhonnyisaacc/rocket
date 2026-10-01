from __future__ import annotations

import json
from pathlib import Path

from scripts.research.memecoin_tx_accounting import select, token_amounts


def test_sample_selection_is_stratified_without_duplicate_signatures(tmp_path: Path):
    rows = [
        {"event_type": "TradeEvent", "signature": f"sig{i}", "slot": i,
         "mint": "mint", "quote_mint": "11111111111111111111111111111111",
         "mayhem_mode": False, "sol_amount": 1, "token_amount": 10,
         "is_buy": i % 2 == 0}
        for i in range(10)
    ]
    rows += [{**rows[0], "signature": "multi", "slot": 11},
             {**rows[1], "signature": "multi", "slot": 11}]
    source = tmp_path / "observations.jsonl"
    source.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = select(tmp_path)
    assert result["population"] == {"single_buy": 5, "single_sell": 5, "multi_trade": 1}
    assert len(result["selected"]) == 11
    assert len({row["signature"] for row in result["selected"]}) == 11


def test_token_account_delta_uses_integer_amount_for_new_and_closed_accounts():
    def balance(index: int, amount: str) -> dict:
        return {"accountIndex": index, "mint": "mint", "uiTokenAmount": {"amount": amount}}

    meta = {"preTokenBalances": [balance(1, "100")],
            "postTokenBalances": [balance(2, "100")]}
    assert token_amounts(meta, "mint") == {1: -100, 2: 100}
