"""Offline MC-014 source agreement and decision-clock signed owner audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from scripts.research.memecoin_audit import NATIVE_QUOTE, PUMP_PROGRAM
from scripts.research.memecoin_flow_diagnostics import percentile
from scripts.research.memecoin_user_owner_audit import event_sized_account_owner


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def expected_selection(observations: list[dict]) -> tuple[list[dict], list[dict]]:
    creates = [row for row in observations if row["event_type"] == "CreateEvent"]
    native = {row["mint"]: row for row in creates if row["quote_mint"] == NATIVE_QUOTE
              and not row["is_mayhem_mode"]}
    candidates: dict[str, list[dict]] = defaultdict(list)
    for row in observations:
        if row["event_type"] != "TradeEvent" or not row["is_buy"]:
            continue
        created = native.get(row["mint"])
        if created is None:
            continue
        at = datetime.fromisoformat(row["available_at"])
        start = datetime.fromisoformat(created["available_at"])
        if start <= at <= start + timedelta(seconds=5):
            candidates[row["mint"]].append(row)
    expected = []
    for mint, candidates_for_mint in candidates.items():
        created = native[mint]
        seen = set()
        for event in sorted(candidates_for_mint, key=lambda row: (
                row["available_at"], row["signature"], row["log_index"])):
            if event["signature"] in seen:
                continue
            seen.add(event["signature"])
            expected.append({"signature": event["signature"], "slot": event["slot"],
                             "mint": mint, "create_signature": created["signature"],
                             "create_received_at": created["available_at"],
                             "event_received_at": event["available_at"],
                             "checkpoint_at": (datetime.fromisoformat(
                                 created["available_at"]) + timedelta(seconds=5)).isoformat(),
                             "event_user": event["user"],
                             "event_token_amount": event["token_amount"],
                             "event_sha256": event["event_sha256"],
                             "frame_source_hash": event["source_hash"]})
            if len(seen) == 3:
                break
    return creates, expected


def evaluate(session: Path, companion: Path) -> dict:
    audit_path = session / "audit.json"
    audit = json.loads(audit_path.read_text())
    capture_path = session / "capture-manifest.json"
    capture = json.loads(capture_path.read_text())
    companion_path = companion / "companion-manifest.json"
    manifest = json.loads(companion_path.read_text())
    if (manifest["source_capture_manifest_sha256"] != digest(capture_path)
            or manifest["source_segment_sha256"] != capture["segment_sha256"]):
        raise ValueError("companion source differs from primary capture")
    observed = rows(session / "observations.jsonl")
    audited_creates, audited_selected = expected_selection(observed)
    captured_creates = rows(companion / "creates.jsonl")
    captured_selected = rows(companion / "selected.jsonl")
    quarantine = {row["signature"] for row in audit.get("quarantined_notifications", [])}
    expected_creates = {row["signature"]: {
        "signature": row["signature"], "slot": row["slot"], "mint": row["mint"],
        "quote_mint": row["quote_mint"], "is_mayhem_mode": row["is_mayhem_mode"],
        "received_at": row["available_at"], "event_sha256": row["event_sha256"],
        "frame_source_hash": row["source_hash"]} for row in audited_creates}
    captured_create_map = {row["signature"]: row for row in captured_creates
                           if row["signature"] not in quarantine}
    create_mismatch = expected_creates != captured_create_map
    expected_by_key = {(row["mint"], row["signature"]): row for row in audited_selected}
    captured_by_key = {(row["mint"], row["signature"]): row for row in captured_selected
                       if row["signature"] not in quarantine}
    selection_mismatches = []
    for key in sorted(expected_by_key.keys() | captured_by_key.keys()):
        if expected_by_key.get(key) != captured_by_key.get(key):
            selection_mismatches.append(key)
    missing_responses = [row["signature"] for row in captured_selected if not (
        companion / "responses" / f"{row['signature']}.json").exists()]
    data_gate = (audit["coverage_status"] == "SIGNATURES_MATCH_INNER_SLOTS"
                 and not audit["capture_errors"] and not audit["index_errors"]
                 and audit["successful_transactions_with_truncated_logs"] == 0
                 and audit["event_decode_error_count"] == 0
                 and not audit["event_transaction_identity_mismatches"]
                 and audit["created_mint_trade_state_continuity"]["native_nonmayhem_fail"] == 0
                 and audit["native_nonmayhem_quote_validation"]["fail"] == 0
                 and manifest["end_reason"] == "capture_finished_and_requests_attempted"
                 and manifest["parsed_frame_count"] == capture["frames"]
                 and manifest["decoded_create_count"] == len(captured_creates)
                 and manifest["selected_buy_count"] == len(captured_selected)
                 and manifest["response_file_count"] == len(list((companion /
                     "responses").glob("*.json")))
                 and not manifest["errors"] and not create_mismatch
                 and not selection_mismatches and not missing_responses)
    inner_start, inner_end = audit["inner_slot_bounds"]
    native_core = [row for row in audited_creates if inner_start <= row["slot"] <= inner_end
                   and row["quote_mint"] == NATIVE_QUOTE and not row["is_mayhem_mode"]]
    native_core_signatures = {row["signature"] for row in native_core}
    selected_core = [row for row in audited_selected if inner_start <= row["slot"] <= inner_end
                     and row["create_signature"] in native_core_signatures]
    result_rows = []
    for chosen in selected_core:
        path = companion / "responses" / f"{chosen['signature']}.json"
        row = {**chosen, "status": "RESPONSE_MISSING", "owner_available_by_checkpoint": False,
               "response_sha256": digest(path) if path.exists() else None}
        if not path.exists():
            result_rows.append(row)
            continue
        saved = json.loads(path.read_text())
        row["attempts"] = len(saved["attempts"])
        successful = next((item for item in saved["attempts"]
                           if item.get("http_status") == 200
                           and item.get("body", {}).get("result")), None)
        if successful is None:
            row["status"] = "TRANSACTION_UNAVAILABLE"
            row["response_statuses"] = [item.get("http_status", item.get("error"))
                                        for item in saved["attempts"]]
            result_rows.append(row)
            continue
        row["retrieved_at"] = successful["received_at"]
        row["retrieval_lag_seconds"] = (datetime.fromisoformat(successful["received_at"])
                                        - datetime.fromisoformat(chosen["event_received_at"])
                                        ).total_seconds()
        tx = successful["body"]["result"]
        if (chosen["signature"] not in tx["transaction"]["signatures"]
                or chosen["slot"] != tx["slot"]):
            row["status"] = "IDENTITY_MISMATCH"
            result_rows.append(row)
            continue
        meta = tx.get("meta")
        if not isinstance(meta, dict) or meta.get("err") is not None:
            row["status"] = "TRANSACTION_FAILED"
            result_rows.append(row)
            continue
        owner = event_sized_account_owner(meta, chosen["mint"],
                                          chosen["event_token_amount"])
        keys = tx["transaction"]["message"]["accountKeys"]
        signers = {item["pubkey"] for item in keys if item.get("signer")}
        row.update({"status": "OWNER_IDENTIFIED" if owner else "OWNER_AMBIGUOUS",
                    "token_account_owner": owner,
                    "event_user_matches_owner": chosen["event_user"] == owner if owner else None,
                    "owner_is_signer": owner in signers if owner else None,
                    "fee_payer": keys[0]["pubkey"],
                    "fee_payer_matches_owner": keys[0]["pubkey"] == owner if owner else None,
                    "top_level_pump": any(item.get("programId") == PUMP_PROGRAM for item in
                                          tx["transaction"]["message"]["instructions"]),
                    "fee_lamports": meta["fee"]})
        row["owner_available_by_checkpoint"] = (owner is not None and
            datetime.fromisoformat(successful["received_at"]) <= datetime.fromisoformat(
                chosen["checkpoint_at"]))
        result_rows.append(row)
    by_create: dict[str, list[dict]] = defaultdict(list)
    for row in result_rows:
        by_create[row["create_signature"]].append(row)
    with_buys = [row for row in native_core if by_create[row["signature"]]]
    complete = sum(all(buy["owner_available_by_checkpoint"] for buy in by_create[
        created["signature"]]) for created in with_buys)
    verified = sum(row["owner_available_by_checkpoint"] for row in result_rows)
    lags = [row["retrieval_lag_seconds"] for row in result_rows
            if "retrieval_lag_seconds" in row]
    useful = (len(result_rows) > 0 and len(with_buys) >= 30
              and verified / len(result_rows) >= 0.8
              and complete / len(with_buys) >= 0.8)
    return {"schema": "rocket.memecoin.mc014-live-actor-audit.v1",
            "audit_sha256": digest(audit_path),
            "companion_manifest_sha256": digest(companion_path),
            "data_gate_pass": data_gate,
            "create_mismatch": create_mismatch,
            "selection_mismatches": selection_mismatches,
            "missing_responses": missing_responses,
            "native_nonmayhem_core_creates": len(native_core),
            "native_creates_with_selected_buys": len(with_buys),
            "native_creates_zero_selected_buys": len(native_core) - len(with_buys),
            "selected_core_buys": len(result_rows),
            "verified_owner_by_checkpoint": verified,
            "verified_owner_by_checkpoint_fraction": (
                verified / len(result_rows) if result_rows else None),
            "all_selected_owners_verified_by_checkpoint_creates": complete,
            "all_selected_owners_verified_by_checkpoint_fraction": (
                complete / len(with_buys) if with_buys else None),
            "owner_identified_later_or_timely": sum(row["status"] == "OWNER_IDENTIFIED"
                                                   for row in result_rows),
            "event_user_owner_match": sum(row.get("event_user_matches_owner") is True
                                          for row in result_rows),
            "routed_top_level": sum(row.get("top_level_pump") is False
                                    for row in result_rows),
            "status_counts": dict(Counter(row["status"] for row in result_rows)),
            "retrieval_lag_seconds": {"median": statistics.median(lags) if lags else None,
                                      "p90": percentile(lags, 0.9)},
            "minimum_useful_availability_gate_pass": data_gate and useful,
            "rows": result_rows,
            "scope": "Signed token-owner availability by five seconds; no beneficial-controller or economic-entry claim."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("companion", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.session, args.companion)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
