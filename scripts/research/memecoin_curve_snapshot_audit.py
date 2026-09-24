"""Offline MC-013 direct Pump-account quote and source-clock audit."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import statistics
import struct
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from rocket.research.pump_events import _base58
from rocket.research.pump_execution import CurveState, FeeSchedule, buy_exact_input, sell
from scripts.research.memecoin_audit import NATIVE_QUOTE, PUMP_PROGRAM
from scripts.research.memecoin_flow_diagnostics import percentile

SIZE = 10_000_000
SLIPPAGE_BPS = 200
FEES = (155_000, 1_000_000)
CURVE_DISCRIMINATOR = bytes([23, 183, 248, 55, 96, 216, 172, 96])


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_curve(value: dict | None) -> dict:
    if value is None:
        raise ValueError("ACCOUNT_MISSING")
    if value.get("owner") != PUMP_PROGRAM:
        raise ValueError("ACCOUNT_OWNER_MISMATCH")
    encoded = value.get("data")
    if not isinstance(encoded, list) or len(encoded) < 2 or encoded[1] != "base64":
        raise ValueError("ACCOUNT_ENCODING_UNSUPPORTED")
    raw = base64.b64decode(encoded[0], validate=True)
    if len(raw) < 125 or raw[:8] != CURVE_DISCRIMINATOR:
        raise ValueError("ACCOUNT_LAYOUT_MISMATCH")
    virtual_tokens, virtual_quote, real_tokens, real_quote, supply = struct.unpack_from(
        "<QQQQQ", raw, 8)
    if any(raw[index] not in (0, 1) for index in (48, 81, 82, 123, 124)):
        raise ValueError("ACCOUNT_BOOL_INVALID")
    return {"virtual_token_reserves": virtual_tokens,
            "virtual_quote_reserves": virtual_quote,
            "real_token_reserves": real_tokens,
            "real_quote_reserves": real_quote,
            "token_total_supply": supply,
            "complete": bool(raw[48]), "creator": _base58(raw[49:81]),
            "is_mayhem_mode": bool(raw[81]), "is_cashback_coin": bool(raw[82]),
            "quote_mint": _base58(raw[83:115]),
            "creator_fee_bps": struct.unpack_from("<Q", raw, 115)[0],
            "can_edit_creator_fee": bool(raw[123]), "is_holder_reward": bool(raw[124]),
            "account_data_sha256": hashlib.sha256(raw).hexdigest(),
            "account_data_len": len(raw)}


def load_reads(companion: Path) -> tuple[dict[tuple[str, str], dict], list[str]]:
    reads = {}
    errors = []
    for path in sorted((companion / "responses").glob("batch-*.json")):
        record = json.loads(path.read_text())
        requested = record["requested"]
        body = record.get("body")
        rpc_result = body.get("result") if isinstance(body, dict) else None
        values = rpc_result.get("value") if isinstance(rpc_result, dict) else None
        context = rpc_result.get("context", {}) if isinstance(rpc_result, dict) else {}
        if values is not None and len(values) != len(requested):
            errors.append(f"BATCH_{record['batch_number']}_RESPONSE_LENGTH_MISMATCH")
            values = None
        for index, item in enumerate(requested):
            key = (item["signature"], item["phase"])
            if key in reads:
                errors.append(f"DUPLICATE_READ_{key[0]}_{key[1]}")
                continue
            target = datetime.fromisoformat(item["target_at"])
            dispatched = datetime.fromisoformat(record["dispatch_at"])
            received = datetime.fromisoformat(record["received_at"])
            result = {**item, "batch_number": record["batch_number"],
                      "response_file_sha256": digest(path),
                      "dispatch_at": record["dispatch_at"],
                      "response_received_at": record["received_at"],
                      "dispatch_lag_seconds": (dispatched - target).total_seconds(),
                      "response_lag_seconds": (received - target).total_seconds(),
                      "http_status": record.get("http_status"),
                      "rpc_error": body.get("error") if isinstance(body, dict) else
                      record.get("error"),
                      "context_slot": context.get("slot")}
            if values is None or record.get("http_status") != 200:
                result["status"] = "RPC_UNAVAILABLE"
            else:
                try:
                    result["account"] = decode_curve(values[index])
                    result["status"] = "ACCOUNT_DECODED"
                except (TypeError, ValueError, KeyError) as exc:
                    result["status"] = "ACCOUNT_UNUSABLE"
                    result["reason"] = str(exc)
            result["timely"] = (result["status"] == "ACCOUNT_DECODED"
                                and 0 <= result["dispatch_lag_seconds"] <= 2
                                and 0 <= result["response_lag_seconds"] <= 5)
            reads[key] = result
    return reads, errors


def reserve_tuple(source: dict, *, event: bool = False) -> tuple[int, int, int, int]:
    quote = "sol" if event else "quote"
    return (source[f"virtual_{quote}_reserves"], source["virtual_token_reserves"],
            source[f"real_{quote}_reserves"], source["real_token_reserves"])


def evaluate(session: Path, companion: Path) -> dict:
    audit_path = session / "audit.json"
    audit = json.loads(audit_path.read_text())
    capture = json.loads((session / "capture-manifest.json").read_text())
    companion_manifest = json.loads((companion / "companion-manifest.json").read_text())
    if companion_manifest["source_capture_manifest_sha256"] != digest(
            session / "capture-manifest.json"):
        raise ValueError("companion source manifest differs from capture")
    if companion_manifest["source_segment_sha256"] != capture["segment_sha256"]:
        raise ValueError("companion source segment differs from capture")
    data_gate = (audit["coverage_status"] == "SIGNATURES_MATCH_INNER_SLOTS"
                 and not audit["capture_errors"] and not audit["index_errors"]
                 and audit["successful_transactions_with_truncated_logs"] == 0
                 and audit["event_decode_error_count"] == 0
                 and not audit["event_transaction_identity_mismatches"]
                 and audit["created_mint_trade_state_continuity"]["native_nonmayhem_fail"] == 0
                 and audit["native_nonmayhem_quote_validation"]["fail"] == 0
                 and not companion_manifest["errors"]
                 and companion_manifest["end_reason"] == "capture_finished_and_reads_attempted"
                 and companion_manifest["parsed_frame_count"] == capture["frames"])
    reads, read_errors = load_reads(companion)
    observations = [json.loads(line) for line in (session / "observations.jsonl").read_text().splitlines()]
    creates = {row["signature"]: row for row in observations if row["event_type"] == "CreateEvent"}
    trades: dict[str, list[dict]] = defaultdict(list)
    for row in observations:
        if row["event_type"] == "TradeEvent":
            trades[row["mint"]].append(row)
    for value in trades.values():
        value.sort(key=lambda row: (row["available_at"], row["slot"],
                                    row["transaction_index"] if row.get(
                                        "transaction_index") is not None else -1,
                                    row["log_index"]))
    companion_creates = [json.loads(line) for line in (companion / "creates.jsonl").read_text(
    ).splitlines()]
    expected_reads = {(row["signature"], phase) for row in companion_creates
                      for phase in ("entry", "exit")}
    missing_reads = sorted(expected_reads - reads.keys())
    unexpected_reads = sorted(reads.keys() - expected_reads)
    create_mismatches = []
    quarantined_signatures = {row["signature"] for row in audit.get(
        "quarantined_notifications", [])}
    audited_create_keys = {(row["signature"], row["mint"]) for row in observations
                           if row["event_type"] == "CreateEvent"}
    companion_create_keys = {(row["signature"], row["mint"]) for row in companion_creates
                             if row["signature"] not in quarantined_signatures}
    for signature, mint in sorted(audited_create_keys - companion_create_keys):
        create_mismatches.append(f"AUDITED_CREATE_NOT_SCHEDULED:{signature}:{mint}")
    for row in companion_creates:
        if row["signature"] in quarantined_signatures:
            continue
        original = creates.get(row["signature"])
        if (original is None or original["mint"] != row["mint"]
                or original["bonding_curve"] != row["bonding_curve"]
                or datetime.fromisoformat(original["available_at"]) != datetime.fromisoformat(
                    row["create_received_at"])):
            create_mismatches.append(row["signature"])
    universe = {row["signature"]: row for line in (session / "universe.jsonl").read_text(
    ).splitlines() if (row := json.loads(line))}
    identity = json.loads((session / "mc013-identity.json").read_text())
    rows = []
    for signature, created in creates.items():
        original = universe.get(signature)
        status = "OUTSIDE_BASELINE_UNIVERSE" if original is None else original["status"]
        row = {"signature": signature, "mint": created["mint"],
               "create_received_at": created["available_at"],
               "baseline_status": status, "baseline_reason": original.get("reason") if original else None,
               "entry": reads.get((signature, "entry")),
               "exit": reads.get((signature, "exit")),
               "identity_status": identity["rows"].get(signature, {}).get("status", "UNVERIFIED"),
               "direct_quote_status": "NOT_ELIGIBLE", "direct_returns": {str(fee): None for fee in FEES}}
        for phase in ("entry", "exit"):
            snapshot = row[phase]
            if snapshot is None:
                continue
            prior = [trade for trade in trades.get(created["mint"], [])
                     if datetime.fromisoformat(trade["available_at"]) <= datetime.fromisoformat(
                         snapshot["response_received_at"])]
            visible = prior[-1] if prior else None
            snapshot["last_visible_trade_signature"] = visible["signature"] if visible else None
            snapshot["account_vs_last_visible_trade_equal"] = (
                reserve_tuple(snapshot["account"]) == reserve_tuple(visible, event=True)
                if visible and snapshot["status"] == "ACCOUNT_DECODED" else None)
            snapshot["context_stale_for_mint"] = (
                snapshot["context_slot"] < visible["slot"]
                if visible and isinstance(snapshot["context_slot"], int) else None)
            snapshot["context_stale_for_create"] = (
                snapshot["context_slot"] < created["slot"]
                if isinstance(snapshot["context_slot"], int) else None)
            snapshot["fee_source_signature"] = visible["signature"] if visible else None
            snapshot["fee_schedule"] = (
                {"protocol_bps": visible["fee_basis_points"],
                 "creator_bps": visible["creator_fee_basis_points"],
                 "creator_enabled": visible["creator"] != NATIVE_QUOTE}
                if visible else None)
        if (not data_gate or read_errors or create_mismatches or missing_reads
                or unexpected_reads or original is None
                or original["score"] is None):
            rows.append(row)
            continue
        if row["identity_status"] not in ("CAPTURED_STRICT", "RECHECKED_STRICT"):
            row["direct_quote_status"] = "IDENTITY_UNVERIFIED"
            rows.append(row)
            continue
        if original["reason"] == "EXIT_OUTSIDE_COVERED_CAPTURE":
            row["direct_quote_status"] = "OUTSIDE_COVERED_LOG_WINDOW"
            rows.append(row)
            continue
        entry, exit_read = row["entry"], row["exit"]
        if not entry or not exit_read or not entry["timely"] or not exit_read["timely"]:
            row["direct_quote_status"] = "SNAPSHOT_MISSING_OR_LATE"
            rows.append(row)
            continue
        if any(not isinstance(read["context_slot"], int) for read in (entry, exit_read)):
            row["direct_quote_status"] = "ACCOUNT_CONTEXT_UNAVAILABLE"
            rows.append(row)
            continue
        if any(read["context_stale_for_create"] or read["context_stale_for_mint"]
               for read in (entry, exit_read)):
            row["direct_quote_status"] = "ACCOUNT_CONTEXT_STALE"
            rows.append(row)
            continue
        if any(read["account"]["quote_mint"] != NATIVE_QUOTE or read["account"][
                "is_mayhem_mode"] for read in (entry, exit_read)):
            row["direct_quote_status"] = "ACCOUNT_REGIME_UNSUPPORTED"
            rows.append(row)
            continue
        if not entry["fee_schedule"] or not exit_read["fee_schedule"]:
            row["direct_quote_status"] = "FEE_STATE_UNAVAILABLE"
            rows.append(row)
            continue
        def state(read: dict) -> CurveState:
            account = read["account"]
            return CurveState(account["virtual_quote_reserves"],
                              account["virtual_token_reserves"],
                              account["real_quote_reserves"],
                              account["real_token_reserves"])

        try:
            if entry["account"]["complete"]:
                raise ValueError("curve complete before entry")
            bought = buy_exact_input(state(entry), SIZE,
                                     FeeSchedule(**entry["fee_schedule"]))
        except ValueError as exc:
            row["direct_quote_status"] = "ENTRY_UNAVAILABLE"
            row["quote_reason"] = str(exc)
            rows.append(row)
            continue
        row["entry_quote"] = bought
        tokens = bought["tokens"] * (10_000 - SLIPPAGE_BPS) // 10_000
        try:
            if exit_read["account"]["complete"]:
                raise ValueError("curve complete")
            exited = sell(state(exit_read), tokens,
                          FeeSchedule(**exit_read["fee_schedule"]))
            exit_cash = exited["cash"] * (10_000 - SLIPPAGE_BPS) // 10_000
            row["exit_quote"] = exited
            row["direct_quote_status"] = "QUOTED"
        except ValueError as exc:
            exit_cash = 0
            row["direct_quote_status"] = "EXIT_UNAVAILABLE"
            row["quote_reason"] = str(exc)
        row["direct_returns"] = {str(fee): (exit_cash - bought["cash"] - 2 * fee) /
                                 (bought["cash"] + fee) for fee in FEES}
        rows.append(row)
    read_rows = [row[phase] for row in rows for phase in ("entry", "exit") if row[phase]]
    eligible = [row for row in rows if row["baseline_status"] != "OUTSIDE_BASELINE_UNIVERSE"
                and universe[row["signature"]]["score"] is not None]
    flow_scores = {row["signature"]: row for line in (
        session / "mc005-flow-rows.jsonl").read_text().splitlines()
        if (row := json.loads(line))}
    for row in eligible:
        original = universe[row["signature"]]
        flow = flow_scores[row["signature"]]
        if original["split"] != flow["split"]:
            raise ValueError("baseline and flow splits differ")
        row["split"] = original["split"]
        row["flow_score"] = flow["flow_score"]
        row["event_state_returns"] = flow["returns"]
        row["direct_minus_event_state"] = {
            str(fee): (row["direct_returns"][str(fee)] - flow["returns"][str(fee)]
                       if row["direct_returns"][str(fee)] is not None
                       and flow["returns"][str(fee)] is not None else None)
            for fee in FEES}

    def group_summary(group: list[dict], fee: int) -> dict:
        quoted = sum(row["direct_quote_status"] == "QUOTED" for row in group)
        unavailable = sum(row["direct_quote_status"] == "EXIT_UNAVAILABLE" for row in group)
        values = [row["direct_returns"][str(fee)] for row in group
                  if row["direct_returns"][str(fee)] is not None]
        differences = [row["direct_minus_event_state"][str(fee)] for row in group
                       if row["direct_minus_event_state"][str(fee)] is not None]
        return {"scored": len(group), "quoted": quoted, "exit_unavailable": unavailable,
                "unknown_or_no_entry": len(group) - quoted - unavailable,
                "stress_n": len(values), "stress_mean": statistics.mean(values) if values else None,
                "stress_median": statistics.median(values) if values else None,
                "paired_event_state_n": len(differences),
                "direct_minus_event_state_median": (
                    statistics.median(differences) if differences else None)}

    splits = {}
    for split in ("development", "evaluation"):
        group = [row for row in eligible if row["split"] == split]
        ranked = sorted(group, key=lambda row: (-row["flow_score"], row["signature"]))
        top = ranked[:(len(ranked) + 3) // 4]
        rest = ranked[len(top):]
        splits[split] = {"scored": len(group), "top_quartile_size": len(top),
                         "fee_scenarios": {str(fee): {
                             "all": group_summary(group, fee),
                             "top_quartile": group_summary(top, fee),
                             "rest": group_summary(rest, fee)} for fee in FEES}}
    result = {"schema": "rocket.memecoin.mc013-direct-curve.v1",
              "audit_sha256": digest(audit_path),
              "companion_manifest_sha256": digest(companion / "companion-manifest.json"),
              "identity_sha256": digest(session / "mc013-identity.json"),
              "data_gate_pass": (data_gate and not read_errors and not create_mismatches
                                 and not missing_reads and not unexpected_reads),
              "read_errors": read_errors, "create_mismatches": create_mismatches,
              "missing_reads": missing_reads, "unexpected_reads": unexpected_reads,
              "all_create_count": len(creates), "baseline_eligible_count": len(eligible),
              "read_status_counts": dict(Counter(row["status"] for row in read_rows)),
              "read_timely_count": sum(row["timely"] for row in read_rows),
              "read_count": len(read_rows),
              "dispatch_lag_seconds": {"median": statistics.median(
                  values) if (values := [row["dispatch_lag_seconds"] for row in read_rows]) else None,
                  "p90": percentile(values, 0.9)},
              "response_lag_seconds": {"median": statistics.median(
                  values) if (values := [row["response_lag_seconds"] for row in read_rows]) else None,
                  "p90": percentile(values, 0.9)},
              "account_vs_visible_trade_equal_count": sum(
                  row["account_vs_last_visible_trade_equal"] is True for row in read_rows),
              "account_vs_visible_trade_compared_count": sum(
                  row["account_vs_last_visible_trade_equal"] is not None for row in read_rows),
              "context_stale_for_mint_count": sum(row["context_stale_for_mint"] is True
                                                  for row in read_rows),
              "context_stale_for_create_count": sum(row["context_stale_for_create"] is True
                                                    for row in read_rows),
              "eligible_direct_status_counts": dict(Counter(row["direct_quote_status"]
                                                           for row in eligible)),
              "baseline_direct_status_counts": dict(Counter(
                  f"{row['baseline_status']}=>{row['direct_quote_status']}" for row in eligible)),
              "flow_split_descriptive": splits,
              "rows": rows,
              "scope": "Read-only contemporaneous curve account quotes; no achieved order fills or alternate exit route."}
    for fee in FEES:
        values = [row["direct_returns"][str(fee)] for row in eligible
                  if row["direct_returns"][str(fee)] is not None]
        result[f"eligible_stress_{fee}"] = {"n": len(values),
                                           "mean": statistics.mean(values) if values else None,
                                           "median": statistics.median(values) if values else None}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("companion", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.session, args.companion)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
