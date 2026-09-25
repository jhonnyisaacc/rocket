"""Retrospectively corroborate MC-010 fast create identities without backdating them."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from scripts.research.memecoin_audit import decode_create_v2

RPC = "https://solana-rpc.publicnode.com"


def fast_scored(session: Path) -> dict[str, dict]:
    creates = {row["signature"]: row for line in
               (session / "observations.jsonl").read_text().splitlines()
               if (row := json.loads(line))["event_type"] == "CreateEvent"}
    result = {}
    for line in (session / "mc005-flow-rows.jsonl").read_text().splitlines():
        row = json.loads(line)
        created = creates[row["signature"]]
        age = (datetime.fromisoformat(created["available_at"]) -
               datetime.fromisoformat(created["event_time"])).total_seconds()
        if age <= 5:
            result[row["signature"]] = {"mint": row["mint"],
                                        "event_available_at": created["available_at"],
                                        "event_age_seconds": age}
    return result


def fetch(session: Path, response_dir: Path, pace_seconds: float) -> None:
    candidates = fast_scored(session)
    audit = json.loads((session / "audit.json").read_text())
    captured = {row["signature"]: row for row in audit["decoded_create_v2"]
                if row["signature"] in candidates and row["mint"] == candidates[
                    row["signature"]]["mint"]}
    response_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=20) as client:
        for signature in sorted(set(candidates) - set(captured)):
            path = response_dir / f"{signature}.json"
            if path.exists() and any(item.get("body", {}).get("result") for item in
                                     json.loads(path.read_text())["attempts"]):
                continue
            attempts = json.loads(path.read_text())["attempts"] if path.exists() else []
            for attempt in range(1, 4):
                requested_at = datetime.now(UTC).isoformat()
                try:
                    response = client.post(RPC, json={"jsonrpc": "2.0", "id": 1,
                                                      "method": "getTransaction", "params": [
                                                          signature, {"encoding": "jsonParsed",
                                                                      "commitment": "confirmed",
                                                                      "maxSupportedTransactionVersion": 1}]})
                    item = {"requested_at": requested_at,
                            "received_at": datetime.now(UTC).isoformat(),
                            "status_code": response.status_code, "body": response.json()}
                except (httpx.HTTPError, ValueError) as exc:
                    item = {"requested_at": requested_at,
                            "error": f"{type(exc).__name__}:{exc}"}
                attempts.append(item)
                if item.get("body", {}).get("result"):
                    break
                time.sleep(pace_seconds * attempt)
            path.write_text(json.dumps({"signature": signature, "rpc_host":
                                        "solana-rpc.publicnode.com", "attempts": attempts},
                                       indent=2) + "\n")
            time.sleep(pace_seconds)


def audit_identity(session: Path, response_dir: Path) -> dict:
    candidates = fast_scored(session)
    audit = json.loads((session / "audit.json").read_text())
    captured = {row["signature"]: row for row in audit["decoded_create_v2"]}
    rows = {}
    for signature, candidate in sorted(candidates.items()):
        original = captured.get(signature)
        if original and original["mint"] == candidate["mint"]:
            rows[signature] = {**candidate, "status": "CAPTURED_STRICT",
                               "identity_available_at": original["identity_available_at"],
                               "transaction_source_hash": original["transaction_source_hash"]}
            continue
        path = response_dir / f"{signature}.json"
        if not path.exists():
            rows[signature] = {**candidate, "status": "UNRESOLVED",
                               "reason": "response_not_saved"}
            continue
        saved = json.loads(path.read_text())
        successful = next((item for item in reversed(saved["attempts"])
                           if item.get("body", {}).get("result")), None)
        if successful is None:
            rows[signature] = {**candidate, "status": "UNRESOLVED",
                               "reason": "transaction_unavailable",
                               "response_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            continue
        try:
            decoded = decode_create_v2(successful["body"], signature)
            if decoded["mint"] != candidate["mint"]:
                raise ValueError("event and create_v2 mint differ")
            status, reason = "RECHECKED_STRICT", None
        except (KeyError, TypeError, ValueError) as exc:
            status, reason = "UNRESOLVED", str(exc)
        rows[signature] = {**candidate, "status": status, "reason": reason,
                           "identity_available_at": successful["received_at"],
                           "response_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return {"schema": "rocket.memecoin.mc010-create-identity.v1",
            "audit_sha256": hashlib.sha256((session / "audit.json").read_bytes()).hexdigest(),
            "flow_rows_sha256": hashlib.sha256((session / "mc005-flow-rows.jsonl").read_bytes()).hexdigest(),
            "fast_scored_count": len(candidates),
            "captured_strict_count": sum(row["status"] == "CAPTURED_STRICT" for row in rows.values()),
            "rechecked_strict_count": sum(row["status"] == "RECHECKED_STRICT" for row in rows.values()),
            "unresolved_count": sum(row["status"] == "UNRESOLVED" for row in rows.values()),
            "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--pace-seconds", type=float, default=1.2)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.fetch:
        fetch(args.session, args.responses, args.pace_seconds)
    result = audit_identity(args.session, args.responses)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
