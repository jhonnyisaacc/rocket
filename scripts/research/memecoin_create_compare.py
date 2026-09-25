"""Corroborate third-party create notifications and compare paired receive clocks."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from rocket.capture.spool import replay_segment
from rocket.research.pump_events import EventDecodeError, PumpEventDecoder
from scripts.research.memecoin_audit import IDL_PATH, pump_data_logs

RPC = "https://solana-rpc.publicnode.com"


def percentile(values: list[float], fraction: float) -> float | None:
    return sorted(values)[int((len(values) - 1) * fraction)] if values else None


def summary(values: list[float]) -> dict:
    return {"n": len(values), "median": statistics.median(values) if values else None,
            "p90": percentile(values, 0.9), "p99": percentile(values, 0.99),
            "min": min(values) if values else None, "max": max(values) if values else None}


def portal_rows(session: Path) -> tuple[dict[str, dict], list[dict]]:
    manifest = json.loads((session / "capture-manifest.json").read_text())
    segment = session / manifest["segment"]
    if hashlib.sha256(segment.read_bytes()).hexdigest() != manifest["segment_sha256"]:
        raise ValueError("PumpPortal capture checksum mismatch")
    rows: dict[str, dict] = {}
    conflicts = []
    frames = 0
    for raw, received_at, _ in replay_segment(segment):
        frames += 1
        item = json.loads(raw)
        if item.get("txType") != "create":
            continue
        signature = item["signature"]
        row = {"signature": signature, "mint": item["mint"],
               "pool": item.get("pool"),
               "received_at": received_at.isoformat(),
               "source_hash": hashlib.sha256(raw).hexdigest()}
        if signature in rows:
            conflicts.append({"signature": signature, "first": rows[signature], "later": row})
        else:
            rows[signature] = row
    if frames != manifest["frames"] or len(rows) + len(conflicts) != manifest["create_notifications"]:
        raise ValueError("PumpPortal manifest count mismatch")
    return rows, conflicts


def fetch_responses(rows: dict[str, dict], response_dir: Path, pace_seconds: float) -> None:
    response_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=20) as client:
        for signature in sorted(rows):
            path = response_dir / f"{signature}.json"
            if path.exists():
                continue
            attempts = []
            for attempt in range(1, 4):
                requested_at = datetime.now().astimezone().isoformat()
                try:
                    response = client.post(RPC, json={"jsonrpc": "2.0", "id": 1,
                                                      "method": "getTransaction", "params": [
                                                          signature, {"encoding": "jsonParsed",
                                                                      "commitment": "confirmed",
                                                                      "maxSupportedTransactionVersion": 1}]})
                    body = response.json()
                    attempts.append({"attempt": attempt, "requested_at": requested_at,
                                     "received_at": datetime.now().astimezone().isoformat(),
                                     "status_code": response.status_code, "body": body})
                    if response.status_code == 200 and body.get("result"):
                        break
                except (httpx.HTTPError, ValueError) as exc:
                    attempts.append({"attempt": attempt, "requested_at": requested_at,
                                     "error": f"{type(exc).__name__}:{exc}"})
                time.sleep(max(pace_seconds, 0.5) * attempt)
            path.write_text(json.dumps({"signature": signature, "rpc_host":
                                        "solana-rpc.publicnode.com", "attempts": attempts},
                                       indent=2) + "\n")
            time.sleep(pace_seconds)


def transaction_identity(path: Path, decoder: PumpEventDecoder) -> dict:
    saved = json.loads(path.read_text())
    response = next((attempt["body"]["result"] for attempt in reversed(saved["attempts"])
                     if attempt.get("body", {}).get("result")), None)
    if response is None:
        return {"status": "TRANSACTION_UNAVAILABLE"}
    if saved["signature"] not in response["transaction"]["signatures"]:
        return {"status": "SIGNATURE_MISMATCH"}
    if response["meta"]["err"] is not None:
        return {"status": "TRANSACTION_FAILED", "slot": response["slot"]}
    logs = response["meta"].get("logMessages") or []
    mints = []
    for _, encoded in pump_data_logs(logs):
        if " " in encoded:
            continue
        try:
            event = decoder.decode(encoded)
        except EventDecodeError as exc:
            return {"status": "EVENT_DECODE_ERROR", "slot": response["slot"],
                    "reason": str(exc)}
        if event and event["event_type"] == "CreateEvent":
            mints.append(event["fields"]["mint"])
    return {"status": "CHAIN_TRANSACTION", "slot": response["slot"],
            "block_time": response.get("blockTime"), "create_event_mints": mints,
            "logs_truncated": "Log truncated" in logs,
            "response_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def compare(portal: Path, solana: Path, response_dir: Path) -> dict:
    portal_manifest = json.loads((portal / "capture-manifest.json").read_text())
    chain_manifest = json.loads((solana / "capture-manifest.json").read_text())
    audit = json.loads((solana / "audit.json").read_text())
    portal_data, duplicates = portal_rows(portal)
    decoder = PumpEventDecoder(IDL_PATH)
    identity = {signature: transaction_identity(response_dir / f"{signature}.json", decoder)
                for signature in portal_data}
    chain_creates = {}
    chain_create_collisions = []
    for line in (solana / "observations.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row["event_type"] != "CreateEvent":
            continue
        if row["signature"] in chain_creates:
            chain_create_collisions.append(row["signature"])
        else:
            chain_creates[row["signature"]] = row
    start = max(datetime.fromisoformat(portal_manifest["subscription_ack_at"]),
                datetime.fromisoformat(chain_manifest["subscription_ack_at"])) + timedelta(seconds=5)
    end = min(datetime.fromisoformat(portal_manifest["ended_at"]),
              datetime.fromisoformat(chain_manifest["ended_at"])) - timedelta(seconds=5)
    if end <= start:
        raise ValueError("common subscription interval too short")
    low, high = audit["inner_slot_bounds"]
    chain_core = {sig: row for sig, row in chain_creates.items()
                  if low <= row["slot"] <= high
                  and start <= datetime.fromisoformat(row["available_at"]) <= end}
    portal_core = {sig: row for sig, row in portal_data.items()
                   if start <= datetime.fromisoformat(row["received_at"]) <= end
                   and low <= identity[sig].get("slot", -1) <= high}
    matched = set(chain_core) & set(portal_data)
    paired = [(datetime.fromisoformat(portal_data[sig]["received_at"]) -
               datetime.fromisoformat(chain_core[sig]["available_at"])).total_seconds()
              for sig in matched]
    ages = [(datetime.fromisoformat(row["received_at"]).timestamp() -
             identity[sig]["block_time"])
            for sig, row in portal_core.items() if isinstance(identity[sig].get("block_time"), int)]
    mismatches = sorted(sig for sig in matched if portal_data[sig]["mint"] != chain_core[sig]["mint"])
    uncorroborated = sorted(sig for sig, result in identity.items()
                           if result["status"] != "CHAIN_TRANSACTION"
                           or portal_data[sig]["mint"] not in result.get("create_event_mints", []))
    missing = sorted(set(chain_core) - set(portal_data))
    portal_extra = sorted(set(portal_core) - set(chain_creates))
    native_nonmayhem = {sig for sig, row in chain_core.items()
                        if row["quote_mint"] == "11111111111111111111111111111111"
                        and not row["is_mayhem_mode"]}
    return {"schema": "rocket.memecoin.mc009-create-compare.v1",
            "portal_manifest_sha256": hashlib.sha256((portal / "capture-manifest.json").read_bytes()).hexdigest(),
            "chain_manifest_sha256": hashlib.sha256((solana / "capture-manifest.json").read_bytes()).hexdigest(),
            "chain_audit_sha256": hashlib.sha256((solana / "audit.json").read_bytes()).hexdigest(),
            "common_core_interval": [start.isoformat(), end.isoformat()],
            "verified_inner_slot_bounds": [low, high],
            "chain_coverage": audit["coverage_status"],
            "chain_truncated_successful_logs": audit["successful_transactions_with_truncated_logs"],
            "portal_capture_errors": portal_manifest["errors"],
            "chain_capture_errors": chain_manifest["errors"],
            "portal_unique_creates": len(portal_data), "portal_duplicate_count": len(duplicates),
            "portal_duplicate_sample": duplicates[:10],
            "chain_create_events": len(chain_creates) + len(chain_create_collisions),
            "chain_core_creates": len(chain_core),
            "chain_create_signature_collision_count": len(chain_create_collisions),
            "chain_create_signature_collision_sample": chain_create_collisions[:20],
            "portal_core_creates": len(portal_core), "paired_creates": len(paired),
            "chain_core_missing_from_portal_count": len(missing),
            "chain_core_missing_from_portal_sample": missing[:20],
            "portal_core_absent_from_all_chain_create_events_count": len(portal_extra),
            "portal_core_absent_from_all_chain_create_events_sample": portal_extra[:20],
            "portal_pool_counts": dict(Counter(row["pool"] for row in portal_data.values())),
            "portal_extra_pool_counts": dict(Counter(portal_core[sig]["pool"]
                                                     for sig in portal_extra)),
            "chain_missing_quote_counts": dict(Counter(chain_core[sig]["quote_mint"]
                                                       for sig in missing)),
            "native_nonmayhem_chain_core_count": len(native_nonmayhem),
            "native_nonmayhem_present_in_portal_count": len(native_nonmayhem & set(portal_data)),
            "mint_mismatch_count": len(mismatches), "mint_mismatch_sample": mismatches[:20],
            "portal_transaction_uncorroborated_count": len(uncorroborated),
            "portal_transaction_uncorroborated_sample": uncorroborated[:20],
            "portal_minus_solana_receipt_seconds": summary(paired),
            "portal_more_than_5_seconds_later_count": sum(value > 5 for value in paired),
            "solana_more_than_5_seconds_later_count": sum(value < -5 for value in paired),
            "portal_blocktime_to_receipt_seconds": summary(ages),
            "portal_eligible_for_longer_test": (
                audit["coverage_status"] == "SIGNATURES_MATCH_INNER_SLOTS"
                and not portal_manifest["errors"] and not chain_manifest["errors"]
                and not duplicates and not chain_create_collisions
                and not missing and not portal_extra and not mismatches
                and not uncorroborated and percentile(ages, 0.9) is not None
                and percentile(ages, 0.9) <= 5),
            "transaction_identity": identity}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("portal", type=Path)
    parser.add_argument("solana", type=Path)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--pace-seconds", type=float, default=0.5)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows, _ = portal_rows(args.portal)
    if args.fetch:
        fetch_responses(rows, args.responses, args.pace_seconds)
    result = compare(args.portal, args.solana, args.responses)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "transaction_identity"}, indent=2))
