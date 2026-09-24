from __future__ import annotations

import json

import pytest

from scripts.research.memecoin_buyer_dispersion import digest, dispersion, evaluate, summarize


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


def test_economic_evaluator_preserves_unscored_universe_and_empty_holdout(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    universe = [
        {"signature": "s1", "mint": "m1", "split": "development", "status": "QUOTED",
         "score": 0.2},
        {"signature": "s2", "mint": "m2", "split": None, "status": "EXCLUDED",
         "score": None},
    ]
    (session / "audit.json").write_text("{}")
    (session / "mc015-identity.json").write_text("{}")
    (session / "universe.jsonl").write_text("".join(json.dumps(row) + "\n" for row in universe))
    direct_path = tmp_path / "direct.json"
    direct_path.write_text(json.dumps({"data_gate_pass": True,
                                       "audit_sha256": digest(session / "audit.json"),
                                       "identity_sha256": digest(session / "mc015-identity.json"),
                                       "rows": [
        {"signature": "s1", "identity_status": "RECHECKED_STRICT", "flow_score": 2,
         "direct_quote_status": "QUOTED", "direct_returns": {"155000": 0.1,
                                                           "1000000": -0.1},
         "direct_minus_event_state": {"155000": 0.0, "1000000": 0.0}},
        {"signature": "s2", "identity_status": "UNVERIFIED", "flow_score": None,
         "direct_quote_status": "NOT_ELIGIBLE", "direct_returns": {"155000": None,
                                                                "1000000": None}},
    ]}))
    actor_path = tmp_path / "actor.json"
    actor_path.write_text(json.dumps({"data_gate_pass": True,
                                      "audit_sha256": digest(session / "audit.json"), "rows": [
        {"create_signature": "s1", "signature": "buy1", "token_account_owner": "owner1",
         "event_sol_amount": 10, "owner_available_by_checkpoint": True},
        {"create_signature": "s1", "signature": "buy2", "token_account_owner": "owner2",
         "event_sol_amount": 10, "owner_available_by_checkpoint": True},
    ]}))
    result = evaluate(session, direct_path, actor_path)
    assert result["universe_count"] == 2
    assert result["score_known_count"] == 1
    assert result["score_status_counts"] == {"SCORED": 1, "BASELINE_EXCLUDED": 1}
    assert result["rows"][0]["score"] == 1
    assert result["rows"][1]["score"] is None
    assert result["evaluation"]["fees"]["155000"]["all"]["stress_mean"] is None
    assert result["minimum_economic_candidate_gate_pass"] is False
