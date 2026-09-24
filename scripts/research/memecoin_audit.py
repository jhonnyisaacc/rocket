"""Reconcile a bounded Pump log capture with independent Solana RPC signatures.

This audits stream coverage, not Pump instruction decoding or trade outcomes.
It makes bounded read-only RPC calls and preserves every response used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from contextlib import nullcontext
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import httpx

from rocket.capture.spool import replay_segment
from rocket.research.pump_events import EventDecodeError, PumpEventDecoder
from rocket.research.pump_execution import (
    FeeSchedule,
    buy_exact_input,
    buy_exact_output,
    pre_trade_state,
    sell,
)
from rocket.workflows.memecoin import canonical_identity

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
CREATE_V2 = hashlib.sha256(b"global:create_v2").digest()[:8]
PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
NATIVE_QUOTE = "11111111111111111111111111111111"
IDL_PATH = Path(__file__).resolve().parents[2] / "docs/research/memecoin/protocol/pump-81091419.json"


def base58_decode(value: str) -> bytes:
    number = 0
    for char in value:
        number = number * 58 + ALPHABET.index(char)
    return b"\0" * (len(value) - len(value.lstrip("1"))) + number.to_bytes(
        (number.bit_length() + 7) // 8, "big")


def decode_create_v2(response: dict, signature: str) -> dict:
    tx = response.get("result")
    if not isinstance(tx, dict) or tx.get("meta", {}).get("err") is not None:
        raise ValueError("create transaction unavailable or failed")
    if signature not in tx["transaction"]["signatures"]:
        raise ValueError("transaction signature mismatch")
    message = tx["transaction"]["message"]
    creates = [item for item in message["instructions"]
               if item.get("programId") == PUMP_PROGRAM
               and base58_decode(item.get("data", ""))[:8] == CREATE_V2]
    if len(creates) != 1:
        raise ValueError("exactly one top-level create_v2 required")
    accounts = creates[0]["accounts"]
    if len(accounts) < 16:
        raise ValueError("create_v2 account list incomplete")
    mint = accounts[0]
    signers = {item["pubkey"] for item in message["accountKeys"] if item.get("signer")}
    if mint not in signers or canonical_identity({"chain_id": "solana:mainnet", "mint": mint}) is None:
        raise ValueError("create_v2 mint identity or signature invalid")
    return {"mint": mint, "slot": tx["slot"], "block_time": tx.get("blockTime"),
            "instruction": "create_v2", "quote_mint": accounts[16] if len(accounts) >= 19 else
            "So11111111111111111111111111111111111111112"}


def audit(session: Path, *, rpc_url: str, max_pages: int, offline: bool = False,
          resume: bool = False, pace_seconds: float = 0) -> dict:
    manifest = json.loads((session / "capture-manifest.json").read_text())
    segment = session / manifest["segment"]
    digest = hashlib.sha256(segment.read_bytes()).hexdigest()
    if digest != manifest["segment_sha256"]:
        raise ValueError("raw segment checksum mismatch")
    notifications: dict[str, dict] = {}
    transaction_frames: dict[str, dict] = {}
    decoder = PumpEventDecoder(IDL_PATH)
    observations: list[dict] = []
    decode_errors: list[dict] = []
    duplicate_notifications = 0
    create_hints: list[dict] = []
    frame_count = 0
    for raw, received_at, _ in replay_segment(segment):
        frame_count += 1
        message = json.loads(raw)
        if message.get("source") == "rpc:getTransaction" and message.get("response", {}).get("result"):
            signature = message["signature"]
            if signature not in transaction_frames:
                transaction_frames[signature] = {
                    "response": message["response"],
                    "available_at": received_at.isoformat(),
                    "source_hash": hashlib.sha256(raw).hexdigest(),
                }
        if message.get("method") != "logsNotification":
            continue
        result = message["params"]["result"]
        value = result["value"]
        signature = value["signature"]
        slot = result["context"]["slot"]
        if signature in notifications:
            duplicate_notifications += 1
            if notifications[signature]["slot"] != slot:
                raise ValueError("conflicting notification slot")
            continue
        notifications[signature] = {"slot": slot, "received_at": received_at.isoformat()}
        if value.get("err") is None:
            for log_index, line in enumerate(value.get("logs", [])):
                if not line.startswith("Program data: "):
                    continue
                encoded = line.removeprefix("Program data: ")
                if " " in encoded:  # Another program may log multiple fields.
                    continue
                try:
                    event = decoder.decode(encoded)
                except EventDecodeError as exc:
                    decode_errors.append({"signature": signature, "reason": str(exc)})
                    continue
                if event is None:
                    continue
                fields = event["fields"]
                mint = fields["mint"]
                if canonical_identity({"chain_id": "solana:mainnet", "mint": mint}) is None:
                    decode_errors.append({"signature": signature, "reason": "invalid event mint"})
                    continue
                observations.append({
                    "signature": signature,
                    "slot": slot,
                    "log_index": log_index,
                    "event_type": event["event_type"],
                    "mint": mint,
                    "event_time": datetime.fromtimestamp(fields["timestamp"], UTC).isoformat(),
                    "available_at": received_at.isoformat(),
                    "source_hash": hashlib.sha256(raw).hexdigest(),
                    "event_sha256": event["event_sha256"],
                    "idl_sha256": event["idl_sha256"],
                    "quote_mint": fields.get("quote_mint"),
                    "virtual_quote_reserves": fields.get("virtual_quote_reserves"),
                    "real_quote_reserves": fields.get("real_quote_reserves"),
                    "virtual_sol_reserves": fields.get("virtual_sol_reserves"),
                    "real_sol_reserves": fields.get("real_sol_reserves"),
                    "virtual_token_reserves": fields.get("virtual_token_reserves"),
                    "real_token_reserves": fields.get("real_token_reserves"),
                    "token_total_supply": fields.get("token_total_supply"),
                    "is_buy": fields.get("is_buy"),
                    "sol_amount": fields.get("sol_amount"),
                    "token_amount": fields.get("token_amount"),
                    "ix_name": fields.get("ix_name"),
                    "fee_basis_points": fields.get("fee_basis_points"),
                    "fee": fields.get("fee"),
                    "creator_fee_basis_points": fields.get("creator_fee_basis_points"),
                    "creator_fee": fields.get("creator_fee"),
                    "creator": fields.get("creator"),
                    "cashback_fee_basis_points": fields.get("cashback_fee_basis_points"),
                    "holder_rewards_bps": fields.get("holder_rewards_bps"),
                    "mayhem_mode": fields.get("mayhem_mode"),
                    "is_mayhem_mode": fields.get("is_mayhem_mode"),
                    "is_holder_reward": fields.get("is_holder_reward"),
                })
        if value.get("err") is None and any(
            line.endswith(("Instruction: Create", "Instruction: CreateV2"))
            for line in value.get("logs", [])
        ):
            create_hints.append({"signature": signature, "slot": slot,
                                 "received_at": received_at.isoformat()})
    if frame_count != manifest["frames"] or frame_count - 1 < manifest["notifications"]:
        raise ValueError("manifest count does not match replay")
    decoded_creates = []
    unresolved_creates = []
    for hint in create_hints:
        signature = hint["signature"]
        frame = transaction_frames.get(signature)
        if frame is None:
            unresolved_creates.append({"signature": signature, "reason": "transaction_not_captured"})
            continue
        try:
            decoded = decode_create_v2(frame["response"], signature)
            if decoded["slot"] != hint["slot"]:
                raise ValueError("create transaction slot mismatch")
        except (KeyError, ValueError) as exc:
            unresolved_creates.append({"signature": signature, "reason": str(exc)})
            continue
        decoded_creates.append({**hint, **decoded,
                                "identity_available_at": frame["available_at"],
                                "transaction_source_hash": frame["source_hash"]})
    event_create_by_signature = {item["signature"]: item for item in observations
                                 if item["event_type"] == "CreateEvent"}
    identity_mismatches = [item["signature"] for item in decoded_creates
                           if event_create_by_signature.get(item["signature"], {}).get("mint") != item["mint"]]

    index_dir = session / "signature-index"
    index_dir.mkdir(exist_ok=True)
    entries: dict[str, dict] = {}
    anchor = manifest.get("end_index_anchor")
    cursor = anchor.get("signature") if isinstance(anchor, dict) else None
    reached_start = False
    index_errors: list[str] = []
    start_slot = manifest["start_slot"]
    end_slot = manifest["end_slot"]
    if not isinstance(start_slot, int) or not isinstance(end_slot, int):
        index_errors.append("capture_slot_bounds_unavailable")
    else:
        if cursor is None:
            index_errors.append("end_index_anchor_unavailable")
        elif anchor.get("slot", -1) < end_slot:
            index_errors.append("end_index_anchor_precedes_end_slot")
        elif start_slot <= anchor["slot"] <= end_slot:
            entries[cursor] = anchor
        with nullcontext() if offline else httpx.Client(timeout=20) as client:
            for page_number in range(max_pages):
                params = {"limit": 1000, "commitment": "confirmed"}
                if cursor:
                    params["before"] = cursor
                request = {"jsonrpc": "2.0", "id": page_number + 1,
                           "method": "getSignaturesForAddress",
                           "params": [manifest["program_id"], params]}
                path = index_dir / f"page-{page_number:03d}.json"
                try:
                    if offline or (resume and path.exists()):
                        body = json.loads(path.read_text())
                    else:
                        if pace_seconds:
                            time.sleep(pace_seconds)
                        response = client.post(rpc_url, json=request)
                        response.raise_for_status()
                        body = response.json()
                    if not isinstance(body.get("result"), list):
                        raise ValueError("RPC returned no signature list")
                except (httpx.HTTPError, ValueError, OSError) as exc:
                    index_errors.append(
                        f"HTTP_{exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError)
                        else type(exc).__name__)
                    break
                raw_response = json.dumps(body, sort_keys=True, separators=(",", ":"))
                if not offline and not (resume and path.exists()):
                    path.write_text(raw_response + "\n")
                page = body["result"]
                if not page:
                    reached_start = True
                    break
                for item in page:
                    if not isinstance(item.get("slot"), int) or not item.get("signature"):
                        raise ValueError("malformed signature index record")
                    if start_slot <= item["slot"] <= end_slot:
                        entries[item["signature"]] = item
                    if item["slot"] < start_slot:
                        reached_start = True
                cursor = page[-1]["signature"]
                if reached_start:
                    break

    # First/last observed slots can straddle subscription or termination.
    # Compare only slots strictly between them; this says nothing about the
    # uncovered wall-clock tail after the final delivered notification.
    first_slot = manifest.get("first_notification_slot")
    last_slot = manifest.get("last_notification_slot")
    inner_start = (first_slot + 1) if isinstance(first_slot, int) else None
    inner_end = (last_slot - 1) if isinstance(last_slot, int) else None
    observed_inner = {key: value for key, value in notifications.items()
                      if inner_start is not None and inner_start <= value["slot"] <= inner_end}
    indexed_inner = {key: value for key, value in entries.items()
                     if inner_start is not None and inner_start <= value["slot"] <= inner_end}
    missing = sorted(set(indexed_inner) - set(observed_inner))
    extra = sorted(set(observed_inner) - set(indexed_inner))
    lags = []
    for signature in set(indexed_inner) & set(observed_inner):
        block_time = indexed_inner[signature].get("blockTime")
        if isinstance(block_time, int):
            received = datetime.fromisoformat(observed_inner[signature]["received_at"])
            lags.append(received.timestamp() - block_time)
    lags.sort()
    for item in observations:
        item["transaction_index"] = entries.get(item["signature"], {}).get("transactionIndex")
    (session / "observations.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in observations))
    create_by_mint = {item["mint"]: item for item in observations if item["event_type"] == "CreateEvent"}
    continuity = {"native_nonmayhem_pass": 0, "native_nonmayhem_fail": 0,
                  "excluded_mayhem_or_nonnative": 0, "missing_order": 0}
    for mint, created in create_by_mint.items():
        trades = [item for item in observations if item["event_type"] == "TradeEvent"
                  and item["mint"] == mint]
        if created.get("is_mayhem_mode") or created.get("quote_mint") != "11111111111111111111111111111111":
            continuity["excluded_mayhem_or_nonnative"] += max(0, len(trades) - 1)
            continue
        if any(item["transaction_index"] is None for item in trades):
            continuity["missing_order"] += max(0, len(trades) - 1)
            continue
        trades.sort(key=lambda item: (item["slot"], item["transaction_index"], item["log_index"]))
        for earlier, later in pairwise(trades):
            direction = 1 if later["is_buy"] else -1
            before_later = (
                later["virtual_sol_reserves"] - direction * later["sol_amount"],
                later["virtual_token_reserves"] + direction * later["token_amount"],
                later["real_sol_reserves"] - direction * later["sol_amount"],
                later["real_token_reserves"] + direction * later["token_amount"],
            )
            after_earlier = tuple(earlier[field] for field in (
                "virtual_sol_reserves", "virtual_token_reserves", "real_sol_reserves", "real_token_reserves"))
            continuity["native_nonmayhem_pass" if before_later == after_earlier
                       else "native_nonmayhem_fail"] += 1
    quote_checks = {"pass": 0, "fail": 0, "unsupported": 0,
                    "one_lamport_fee_discrepancy": 0, "failure_sample": []}
    for event in observations:
        if event["event_type"] != "TradeEvent":
            continue
        if event["quote_mint"] != NATIVE_QUOTE or event["mayhem_mode"]:
            quote_checks["unsupported"] += 1
            continue
        if event["ix_name"] == "sell" and event["sol_amount"] == 0:
            quote_checks["unsupported"] += 1  # Valid dust transfer, no cash exit.
            continue
        try:
            fees = FeeSchedule(event["fee_basis_points"], event["creator_fee_basis_points"],
                               event["creator"] != NATIVE_QUOTE)
            gross = event["sol_amount"]
            exact_input = event["ix_name"] in ("buy_exact_sol_in", "buy_exact_quote_in")
            expected_protocol = (gross * fees.protocol_bps + 9999) // 10000
            expected_creator = (gross * fees.creator_bps + 9999) // 10000 if fees.creator_enabled else 0
            if exact_input and event["fee"] == expected_protocol + 1 and event[
                "creator_fee"] == expected_creator:
                quote_checks["one_lamport_fee_discrepancy"] += 1
            elif (expected_protocol, expected_creator) != (event["fee"], event["creator_fee"]):
                raise ValueError("fee amount mismatch")
            state = pre_trade_state(event)
            if event["ix_name"] == "buy":
                quote = buy_exact_output(state, event["token_amount"], fees)
            elif event["ix_name"] in ("buy_exact_sol_in", "buy_exact_quote_in"):
                quote = buy_exact_input(state, gross + expected_protocol + expected_creator, fees)
            elif event["ix_name"] == "sell":
                quote = sell(state, event["token_amount"], fees)
            else:
                quote_checks["unsupported"] += 1
                continue
            if (quote["gross"], quote["tokens"]) != (gross, event["token_amount"]):
                raise ValueError("fill amount mismatch")
            quote_checks["pass"] += 1
        except (TypeError, ValueError) as exc:
            quote_checks["fail"] += 1
            if len(quote_checks["failure_sample"]) < 20:
                quote_checks["failure_sample"].append({"signature": event["signature"],
                                                        "reason": str(exc)})
    summary = {
        "schema": "rocket.memecoin.capture-audit.v1",
        "capture_manifest_sha256": hashlib.sha256(
            (session / "capture-manifest.json").read_bytes()).hexdigest(),
        "index_source": "getSignaturesForAddress",
        "end_index_anchor": anchor,
        "index_page_count": len(list(index_dir.glob("page-*.json"))),
        "index_reached_start_slot": reached_start,
        "index_errors": index_errors,
        "raw_frame_count": frame_count,
        "unique_notifications": len(notifications),
        "duplicate_notifications": duplicate_notifications,
        "successful_create_log_hints": create_hints,
        "idl_sha256": decoder.idl_sha256,
        "decoded_event_counts": {
            "CreateEvent": sum(item["event_type"] == "CreateEvent" for item in observations),
            "TradeEvent": sum(item["event_type"] == "TradeEvent" for item in observations),
        },
        "event_decode_error_count": len(decode_errors),
        "event_decode_error_sample": decode_errors[:20],
        "event_transaction_identity_mismatches": identity_mismatches,
        "created_mint_trade_state_continuity": continuity,
        "native_nonmayhem_quote_validation": quote_checks,
        "decoded_create_v2": decoded_creates,
        "unresolved_creates": unresolved_creates,
        "inner_slot_bounds": [inner_start, inner_end],
        "unverified_boundary_slots": [first_slot, last_slot],
        "inner_stream_signatures": len(observed_inner),
        "inner_index_signatures": len(indexed_inner),
        "missing_from_stream_count": len(missing),
        "missing_from_stream_sample": missing[:20],
        "missing_from_index_count": len(extra),
        "missing_from_index_sample": extra[:20],
        "block_timestamp_to_receive_seconds": {
            "n": len(lags),
            "median": statistics.median(lags) if lags else None,
            "p90": lags[int((len(lags) - 1) * 0.9)] if lags else None,
            "min": lags[0] if lags else None,
            "max": lags[-1] if lags else None,
            "precision_note": "RPC blockTime has whole-second precision; this is not exact network latency.",
        },
        "coverage_status": (
            "SIGNATURES_MATCH_INNER_SLOTS"
            if manifest["end_reason"] == "duration_elapsed" and reached_start
            and not index_errors and not missing and not extra
            else "INCOMPLETE_OR_UNVERIFIED"
        ),
    }
    (session / "audit.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--rpc-url", default="https://api.mainnet-beta.solana.com/")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--offline", action="store_true", help="replay saved RPC index pages")
    parser.add_argument("--resume", action="store_true", help="reuse saved pages, fetch later pages")
    parser.add_argument("--pace-seconds", type=float, default=0)
    arguments = parser.parse_args()
    if not 1 <= arguments.max_pages <= 100:
        parser.error("max-pages must be 1..100")
    if not 0 <= arguments.pace_seconds <= 10:
        parser.error("pace-seconds must be 0..10")
    print(json.dumps(audit(arguments.session, rpc_url=arguments.rpc_url,
                           max_pages=arguments.max_pages, offline=arguments.offline,
                           resume=arguments.resume,
                           pace_seconds=arguments.pace_seconds), indent=2))
