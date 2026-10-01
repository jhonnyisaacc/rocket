from __future__ import annotations

import asyncio
import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rocket.research.pump_events import PumpEventDecoder
from scripts.research import memecoin_curve_snapshot_capture as capture_module
from scripts.research.memecoin_audit import IDL_PATH, PUMP_PROGRAM

FIXTURE = json.loads((Path(__file__).parent / "fixtures/pump_events.json").read_text())


def test_create_parser_uses_frame_receipt_and_pinned_event():
    received = "2026-09-24T00:00:00+00:00"
    raw = json.dumps({"method": "logsNotification", "params": {"result": {
        "context": {"slot": 123}, "value": {"signature": "signed-tx", "err": None,
                                             "logs": [f"Program {PUMP_PROGRAM} invoke [1]",
                                                      "Program data: " + FIXTURE["CreateEvent"]["encoded"],
                                                      f"Program {PUMP_PROGRAM} success"]}}}}).encode()
    rows = capture_module.creates_in_frame(
        {"raw_base64": base64.b64encode(raw).decode(), "received_at": received},
        PumpEventDecoder(IDL_PATH))
    assert len(rows) == 1
    assert rows[0]["mint"] == FIXTURE["CreateEvent"]["mint"]
    assert rows[0]["create_received_at"] == received
    assert rows[0]["bonding_curve"]


def test_companion_attempts_both_due_reads_and_saves_full_response(tmp_path, monkeypatch):
    received = (datetime.now(UTC) - timedelta(seconds=80)).isoformat()
    raw = json.dumps({"method": "logsNotification", "params": {"result": {
        "context": {"slot": 123}, "value": {"signature": "signed-tx", "err": None,
                                             "logs": [f"Program {PUMP_PROGRAM} invoke [1]",
                                                      "Program data: " + FIXTURE["CreateEvent"]["encoded"],
                                                      f"Program {PUMP_PROGRAM} success"]}}}}).encode()
    session = tmp_path / "session"
    session.mkdir()
    (session / "segment-000000000000.jsonl").write_text(json.dumps({
        "raw_base64": base64.b64encode(raw).decode(), "received_at": received}) + "\n")
    (session / "capture-manifest.json").write_text(json.dumps({"segment_sha256": "source"}))

    class FakeResponse:
        status_code = 200
        content = b"response"

        def json(self):
            return {"result": {"context": {"slot": 124}, "value": [None, None]}}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, json):
            assert len(json["params"][0]) == 2
            return FakeResponse()

    monkeypatch.setattr(capture_module.httpx, "AsyncClient", FakeClient)
    out = tmp_path / "out"
    result = asyncio.run(capture_module.capture(
        session, out, max_seconds=60, max_bytes=100_000, rpc_url="http://unused"))
    saved = json.loads((out / "responses" / "batch-000000.json").read_text())
    assert result["end_reason"] == "capture_finished_and_reads_attempted"
    assert result["scheduled_read_count"] == 2
    assert result["decoded_create_count"] == 1
    assert {row["phase"] for row in saved["requested"]} == {"entry", "exit"}
    assert saved["body"]["result"]["context"]["slot"] == 124
