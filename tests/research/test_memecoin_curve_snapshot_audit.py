from __future__ import annotations

import base64
import json
import struct
from datetime import UTC, datetime, timedelta

import pytest

from scripts.research.memecoin_audit import NATIVE_QUOTE, PUMP_PROGRAM, base58_decode
from scripts.research.memecoin_curve_snapshot_audit import (
    CURVE_DISCRIMINATOR,
    decode_curve,
    load_reads,
    reserve_tuple,
)


def test_pinned_curve_account_decodes_integer_reserves_and_quote_mint():
    raw = bytearray(151)
    raw[:8] = CURVE_DISCRIMINATOR
    struct.pack_into("<QQQQQ", raw, 8, 1000, 2000, 3000, 4000, 5000)
    raw[48] = 1
    raw[83:115] = base58_decode(NATIVE_QUOTE)
    struct.pack_into("<Q", raw, 115, 25)
    value = {"owner": PUMP_PROGRAM, "data": [base64.b64encode(raw).decode(), "base64"]}
    decoded = decode_curve(value)
    assert decoded["complete"] is True
    assert decoded["quote_mint"] == NATIVE_QUOTE
    assert decoded["creator_fee_bps"] == 25
    assert reserve_tuple(decoded) == (2000, 1000, 4000, 3000)
    assert reserve_tuple({"virtual_sol_reserves": 2000, "virtual_token_reserves": 1000,
                          "real_sol_reserves": 4000, "real_token_reserves": 3000},
                         event=True) == reserve_tuple(decoded)


def test_curve_account_owner_and_layout_are_required():
    value = {"owner": "wrong", "data": [base64.b64encode(bytes(151)).decode(), "base64"]}
    with pytest.raises(ValueError, match="OWNER"):
        decode_curve(value)
    value["owner"] = PUMP_PROGRAM
    with pytest.raises(ValueError, match="LAYOUT"):
        decode_curve(value)


def test_saved_account_read_keeps_late_dispatch_explicit(tmp_path):
    raw = bytearray(151)
    raw[:8] = CURVE_DISCRIMINATOR
    struct.pack_into("<QQQQQ", raw, 8, 1000, 2000, 3000, 4000, 5000)
    raw[83:115] = base58_decode(NATIVE_QUOTE)
    target = datetime(2026, 9, 24, tzinfo=UTC)
    response_dir = tmp_path / "responses"
    response_dir.mkdir()
    (response_dir / "batch-000000.json").write_text(json.dumps({
        "batch_number": 0,
        "requested": [{"signature": "tx", "phase": "exit", "target_at": target.isoformat(),
                       "mint": "mint", "bonding_curve": "curve"}],
        "dispatch_at": (target + timedelta(seconds=3)).isoformat(),
        "received_at": (target + timedelta(seconds=4)).isoformat(),
        "http_status": 200,
        "body": {"result": {"context": {"slot": 123}, "value": [
            {"owner": PUMP_PROGRAM, "data": [base64.b64encode(raw).decode(), "base64"]}]}}}))
    reads, errors = load_reads(tmp_path)
    assert not errors
    assert reads[("tx", "exit")]["status"] == "ACCOUNT_DECODED"
    assert reads[("tx", "exit")]["timely"] is False
    assert reads[("tx", "exit")]["dispatch_lag_seconds"] == 3
