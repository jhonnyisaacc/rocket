from __future__ import annotations

from scripts.research.memecoin_user_owner_audit import event_sized_account_owner


def test_event_sized_token_owner_can_differ_from_router_user():
    meta = {
        "preTokenBalances": [
            {"accountIndex": 1, "mint": "mint", "owner": "original-seller",
             "uiTokenAmount": {"amount": "100"}},
            {"accountIndex": 2, "mint": "mint", "owner": "router",
             "uiTokenAmount": {"amount": "0"}},
        ],
        "postTokenBalances": [
            {"accountIndex": 1, "mint": "mint", "owner": "original-seller",
             "uiTokenAmount": {"amount": "0"}},
            {"accountIndex": 2, "mint": "mint", "owner": "router",
             "uiTokenAmount": {"amount": "0"}},
            {"accountIndex": 3, "mint": "mint", "owner": "curve",
             "uiTokenAmount": {"amount": "100"}},
        ],
    }
    assert event_sized_account_owner(meta, "mint", -100) == "original-seller"
