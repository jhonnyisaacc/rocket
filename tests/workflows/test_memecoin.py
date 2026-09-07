from datetime import UTC, datetime, timedelta

from rocket.capture.spool import RawCaptureSpool, replay_segment
from rocket.models import ResearchStatus
from rocket.workflows.memecoin import MemecoinWorkflow, canonical_identity
from tests.harness import assert_research_result, is_registered

NOW = datetime(2026, 9, 4, tzinfo=UTC)


def snapshot(address="0x" + "1" * 40, **overrides):
    row = {
        "asset": "SAME",
        "chain_id": "eip155:1",
        "contract_address": address,
        "decision_time": NOW.isoformat(),
        "available_at": NOW.isoformat(),
        "features": {"volume_acceleration": 3, "liquidity_usd": 50_000},
    }
    row.update(overrides)
    return row


def test_memecoin_registered():
    assert is_registered("memecoin.scan")


def test_canonical_identity_not_ticker():
    assert canonical_identity(snapshot()) == "eip155:1:" + "0x" + "1" * 40
    assert canonical_identity({"chain_id": "eip155:1", "contract_address": "0x0"}) is None


def test_status_is_no_edge_validated():
    result = MemecoinWorkflow().status(now=NOW)
    assert_research_result(result)
    assert result.payload["edge"] == "NO_EDGE_VALIDATED"
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE


def test_duplicate_identity_rejected():
    result = MemecoinWorkflow().scan([snapshot(), snapshot()], now=NOW)
    assert_research_result(result)
    assert any(row.get("reason") == "duplicate_snapshot_identity" for row in result.payload["rejected"])
    assert result.payload["case_study"] is None


def test_spool_fsync_round_trip(tmp_path):
    spool = RawCaptureSpool(tmp_path, max_bytes=1024 * 1024, reserve_bytes=1)
    received = NOW + timedelta(seconds=1)
    receipts = spool.append_batch([(b"abc", received)])
    spool.close()
    assert receipts[0]["event_id"]
    frames = list(replay_segment(tmp_path / receipts[0]["segment"]))
    assert frames[0][0] == b"abc"
