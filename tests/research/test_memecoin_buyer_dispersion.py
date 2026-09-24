from __future__ import annotations

import pytest

from scripts.research.memecoin_buyer_dispersion import dispersion, summarize


def buy(owner: str, lamports: int) -> dict:
    return {"token_account_owner": owner, "event_sol_amount": lamports}


def test_size_dispersion_aggregates_repeat_owners_before_concentration():
    assert dispersion([buy("a", 10)]) == 0
    assert dispersion([buy("a", 10), buy("a", 10)]) == 0
    assert dispersion([buy("a", 10), buy("b", 10)]) == 1
    assert dispersion([buy("a", 30), buy("b", 10)]) == 0.75
    assert dispersion([buy("a", 10), buy("b", 10), buy("c", 10)]) == 1
    with pytest.raises(ValueError):
        dispersion([buy("a", 0)])


def test_cost_summary_keeps_unknown_exit_out_of_stress_denominator():
    rows = [
        {"direct_quote_status": "QUOTED", "direct_returns": {"155000": 0.1}},
        {"direct_quote_status": "EXIT_UNAVAILABLE", "direct_returns": {"155000": -1.0}},
        {"direct_quote_status": "ACCOUNT_CONTEXT_STALE", "direct_returns": {"155000": None}},
    ]
    result = summarize(rows, 155_000)
    assert result["scored"] == 3
    assert result["known_entry"] == 2
    assert result["quoted"] == 1
    assert result["exit_unavailable"] == 1
    assert result["unknown_or_no_entry"] == 1
    assert result["stress_mean"] == -0.45
