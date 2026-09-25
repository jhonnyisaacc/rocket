"""Audit provider-truncated Pump logs against independently fetched transactions."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from rocket.capture.spool import replay_segment
from rocket.research.pump_events import EventDecodeError, PumpEventDecoder
from scripts.research.memecoin_audit import IDL_PATH, pump_data_logs

RPC = "https://api.mainnet-beta.solana.com"


def truncated_frames(session: Path) -> dict[str, dict]:
    manifest = json.loads((session / "capture-manifest.json").read_text())
    segment = session / manifest["segment"]
    if hashlib.sha256(segment.read_bytes()).hexdigest() != manifest["segment_sha256"]:
        raise ValueError("derived segment checksum mismatch")
    result = {}
    for raw, received_at, _ in replay_segment(segment):
        message = json.loads(raw)
        if message.get("method") != "logsNotification":
            continue
        value = message["params"]["result"]["value"]
        if value["err"] is None and "Log truncated" in value["logs"]:
            result[value["signature"]] = {
                "slot": message["params"]["result"]["context"]["slot"],
                "received_at": received_at.isoformat(),
                "source_hash": hashlib.sha256(raw).hexdigest(), "logs": value["logs"]}
    return result


def fetch(rows: dict[str, dict], response_dir: Path, pace_seconds: float) -> None:
    response_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=20) as client:
        for signature in sorted(rows):
            path = response_dir / f"{signature}.json"
            previous = json.loads(path.read_text()) if path.exists() else None
            if previous and previous.get("body", {}).get("result"):
                continue
            attempts = list(previous.get("attempts", [previous])) if previous else []
            for attempt in range(3):
                requested_at = datetime.now(UTC).isoformat()
                try:
                    response = client.post(RPC, json={"jsonrpc": "2.0", "id": 1,
                                                      "method": "getTransaction", "params": [
                                                          signature, {"encoding": "jsonParsed",
                                                                      "commitment": "confirmed",
                                                                      "maxSupportedTransactionVersion": 1}]})
                    saved = {"signature": signature, "requested_at": requested_at,
                             "received_at": datetime.now(UTC).isoformat(),
                             "status_code": response.status_code, "body": response.json()}
                except (httpx.HTTPError, ValueError) as exc:
                    saved = {"signature": signature, "requested_at": requested_at,
                             "error": f"{type(exc).__name__}:{exc}"}
                attempts.append(saved)
                if saved.get("body", {}).get("result"):
                    break
                time.sleep(pace_seconds * (attempt + 1))
            record = {**saved, "attempts": attempts}
            path.write_text(json.dumps(record, indent=2) + "\n")
            time.sleep(pace_seconds)


def event_counts(logs: list[str], decoder: PumpEventDecoder) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, encoded in pump_data_logs(logs):
        if " " in encoded:
            continue
        try:
            event = decoder.decode(encoded)
        except EventDecodeError:
            counts["DECODE_ERROR"] = counts.get("DECODE_ERROR", 0) + 1
            continue
        if event is not None:
            name = event["event_type"]
            counts[name] = counts.get(name, 0) + 1
    return counts


def audit(session: Path, response_dir: Path) -> dict:
    rows = truncated_frames(session)
    decoder = PumpEventDecoder(IDL_PATH)
    evidence = []
    for signature, source in sorted(rows.items()):
        path = response_dir / f"{signature}.json"
        saved = json.loads(path.read_text())
        tx = saved.get("body", {}).get("result")
        valid = (isinstance(tx, dict) and signature in tx["transaction"]["signatures"]
                 and tx["slot"] == source["slot"] and tx["meta"]["err"] is None)
        independent_logs = tx["meta"].get("logMessages") or [] if valid else []
        source_events = event_counts(source["logs"], decoder)
        independent_events = event_counts(independent_logs, decoder) if valid else {}
        evidence.append({"signature": signature, "slot": source["slot"],
                         "original_received_at": source["received_at"],
                         "retrospective_received_at": saved.get("received_at"),
                         "source_frame_sha256": source["source_hash"],
                         "response_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "transaction_identity_verified": bool(valid),
                         "original_log_lines": len(source["logs"]),
                         "independent_log_lines": len(independent_logs),
                         "independent_logs_truncated": "Log truncated" in independent_logs,
                         "original_events": source_events,
                         "independent_events": independent_events})
    return {"schema": "rocket.memecoin.truncated-log-audit.v1",
            "session_manifest_sha256": hashlib.sha256((session / "capture-manifest.json").read_bytes()).hexdigest(),
            "independent_rpc_host": "api.mainnet-beta.solana.com",
            "truncated_successful_transactions": len(rows),
            "transaction_identities_verified": sum(x["transaction_identity_verified"] for x in evidence),
            "independent_full_log_count": sum(x["transaction_identity_verified"]
                                              and not x["independent_logs_truncated"] for x in evidence),
            "extra_trade_events": sum(x["independent_events"].get("TradeEvent", 0)
                                      - x["original_events"].get("TradeEvent", 0)
                                      for x in evidence if x["transaction_identity_verified"]),
            "rows": evidence}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--pace-seconds", type=float, default=0.5)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = truncated_frames(args.session)
    if args.fetch:
        fetch(rows, args.responses, args.pace_seconds)
    result = audit(args.session, args.responses)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
