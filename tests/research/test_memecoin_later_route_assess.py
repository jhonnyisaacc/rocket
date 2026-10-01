from __future__ import annotations

import json

import pytest

from scripts.research.memecoin_later_route_assess import assess, sha

MINT = "CW1mrqPVKs42MYWfiEePFcKasEzqXsS64rrLwF7kpump"
CANONICAL = "4xhjKom7D17hQm5mASdT8AKGKSKedtY62CpapccNJvk7"


def test_later_canonical_pool_is_not_alternate_route(tmp_path):
    direct = tmp_path / "direct.json"
    direct.write_text(json.dumps({"rows": [{"mint": MINT,
        "direct_quote_status": "EXIT_UNAVAILABLE"}]}))
    responses = tmp_path / "responses"
    responses.mkdir()
    batch = responses / "batch-000.json"
    batch.write_text(json.dumps({"attempts": [{"http_status": 200, "body": [],
        "requested_at": "2026-09-24T00:03:00+00:00",
        "received_at": "2026-09-24T00:03:01+00:00"}]}))
    probe = tmp_path / "probe.json"
    probe.write_text(json.dumps({"response_hashes": [{"batch": 0,
        "sha256": sha(batch)}], "rows": [{"mint": MINT,
        "group": "curve_unavailable",
        "frozen_exit_at": "2026-09-24T00:01:00+00:00",
        "pairs": [{"pair_address": CANONICAL, "dex_id": "pumpswap"}]}]}))
    result = assess(direct, probe, responses)
    group = result["groups"]["curve_unavailable"]
    assert group["listed_canonical_pumpswap"] == 1
    assert group["listed_other_pool_lead"] == 0

    batch.write_text(batch.read_text() + " ")
    with pytest.raises(ValueError, match="digest mismatch"):
        assess(direct, probe, responses)
