import json

import pytest

from scripts.research.memecoin_payer_overlap import digest, evaluate


def test_shared_payer_with_different_owners_and_unknown_buy(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    (session / "audit.json").write_text("{}")
    rows = [
        {"create_signature": "c1", "signature": "b1", "status": "OWNER_IDENTIFIED",
         "owner_available_by_checkpoint": True, "token_account_owner": "o1",
         "fee_payer": "payer", "fee_payer_matches_owner": False,
         "owner_is_signer": True},
        {"create_signature": "c1", "signature": "b2", "status": "OWNER_IDENTIFIED",
         "owner_available_by_checkpoint": True, "token_account_owner": "o2",
         "fee_payer": "payer", "fee_payer_matches_owner": False,
         "owner_is_signer": True},
        {"create_signature": "c2", "signature": "b3", "status": "OWNER_AMBIGUOUS",
         "owner_available_by_checkpoint": False},
    ]
    actor = tmp_path / "actor.json"
    actor.write_text(json.dumps({"data_gate_pass": True,
                                 "audit_sha256": digest(session / "audit.json"),
                                 "selected_core_buys": 3,
                                 "verified_owner_by_checkpoint": 2,
                                 "rows": rows}))
    result = evaluate(session, actor)
    assert result["different_owners_shared_payer_creates"] == 1
    assert result["multi_owner_eligible_creates"] == 1
    assert result["unknown_or_late_buys"] == 1
    assert result["timely_owner_equals_fee_payer_buys"] == 0

    (session / "audit.json").write_text("{\"different\": true}")
    with pytest.raises(ValueError, match="primary audit"):
        evaluate(session, actor)
