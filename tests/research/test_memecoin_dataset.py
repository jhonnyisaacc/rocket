from __future__ import annotations

import pytest

from rocket.research.memecoin_dataset import SnapshotError, build_snapshot

MINT = "So11111111111111111111111111111111111111112"
HASH = "a" * 64


def snapshot(observations):
    return build_snapshot(
        {"chain_id": "solana:mainnet", "mint": MINT},
        observations,
        decision_time="2026-09-24T00:00:10Z",
        lifecycle_stage="bonding_curve",
        discovery_source="pump_create_event",
        protocol_version="pump-layout-observed-v1",
        fee_model_version="unverified",
        quote_mint=MINT,
    )


def observation(**overrides):
    return {
        "name": "real_quote_reserves",
        "value": 100,
        "event_time": "2026-09-24T00:00:01Z",
        "available_at": "2026-09-24T00:00:03Z",
        "source_ref": "slot:1/tx:1",
        "source_hash": HASH,
        **overrides,
    }


def test_snapshot_keeps_feature_provenance_and_deterministic_fingerprint():
    row = snapshot([observation()])
    assert row == snapshot([observation()])
    assert row["provenance"]["real_quote_reserves"]["available_at"] == "2026-09-24T00:00:03+00:00"
    assert row["quote_mint"] == MINT
    assert "outcome" not in row


@pytest.mark.parametrize("bad", [
    {"available_at": "2026-09-24T00:00:11Z"},
    {"event_time": "2026-09-24T00:00:11Z"},
    {"available_at": "2026-09-24T00:00:00Z"},
    {"name": "forward_return"},
    {"source_hash": "not-a-hash"},
])
def test_snapshot_rejects_leakage_and_unverifiable_sources(bad):
    with pytest.raises(SnapshotError):
        snapshot([observation(**bad)])


def test_snapshot_rejects_duplicate_feature_name():
    with pytest.raises(SnapshotError):
        snapshot([observation(), observation(value=101)])
