from __future__ import annotations

import base64
import hashlib
import json

import pytest

from scripts.research.memecoin_amm_landed_audit import (
    event_layout,
    sell_events,
    verify_reply,
)


def test_sell_event_requires_exact_layout_and_amm_invocation():
    discriminator, fields = event_layout()
    sizes = {"u64": 8, "i64": 8, "i128": 16, "pubkey": 32, "bool": 1}
    payload = discriminator + b"".join(bytes(sizes[field["type"]]) for field in fields)
    encoded = base64.b64encode(payload).decode()
    program = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
    events, errors = sell_events([f"Program {program} invoke [1]",
                                 f"Program data: {encoded}",
                                 f"Program {program} success"])
    assert not errors
    assert len(events) == 1
    assert events[0]["fields"]["virtual_quote_reserves"] == 0

    extra = base64.b64encode(payload + b"\0").decode()
    events, errors = sell_events([f"Program {program} invoke [1]",
                                 f"Program data: {extra}",
                                 f"Program {program} success"])
    assert not events
    assert "unknown sell event trailing bytes" in errors


def test_raw_rpc_bytes_are_bound_to_decoded_body():
    raw = b'{"jsonrpc":"2.0","result":[]}'
    reply = {"raw_response_base64": base64.b64encode(raw).decode(),
             "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
             "body": json.loads(raw),
             "dispatch_at": "2026-09-24T00:00:00+00:00",
             "received_at": "2026-09-24T00:00:01+00:00"}
    verify_reply(reply)
    reply["body"]["result"] = [1]
    with pytest.raises(ValueError, match="byte/body mismatch"):
        verify_reply(reply)
