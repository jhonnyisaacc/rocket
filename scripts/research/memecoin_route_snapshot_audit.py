"""Offline MC-017 canonical PumpSwap route and same-bank account audit."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import statistics
import struct
from collections import Counter
from datetime import datetime
from pathlib import Path

from rocket.research.solana_pda import (
    PUMP_AMM_PROGRAM,
    WSOL_MINT,
    canonical_pump_pool,
    encode_base58,
)
from scripts.research.memecoin_audit import NATIVE_QUOTE
from scripts.research.memecoin_curve_snapshot_audit import decode_curve
from scripts.research.memecoin_flow_diagnostics import percentile
from scripts.research.memecoin_route_snapshot_capture import (
    AMM_CONFIG,
    AMM_IDL_PATH,
    POOL_DISCRIMINATOR,
)

TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
CONFIG_DISCRIMINATOR = bytes([149, 8, 156, 202, 160, 252, 176, 217])


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def account_bytes(value: dict | None, owner: str) -> bytes:
    if value is None:
        raise ValueError("ACCOUNT_MISSING")
    if value.get("owner") != owner:
        raise ValueError("ACCOUNT_OWNER_MISMATCH")
    data = value.get("data")
    if not isinstance(data, list) or len(data) != 2 or data[1] != "base64":
        raise ValueError("ACCOUNT_ENCODING_UNSUPPORTED")
    return base64.b64decode(data[0], validate=True)


def decode_pool(value: dict | None, mint: str, authority: str) -> dict:
    raw = account_bytes(value, PUMP_AMM_PROGRAM)
    if len(raw) < 211 or raw[:8] != POOL_DISCRIMINATOR:
        raise ValueError("POOL_LAYOUT_MISMATCH")
    if struct.unpack_from("<H", raw, 9)[0] != 0:
        raise ValueError("POOL_INDEX_NOT_CANONICAL")
    if (encode_base58(raw[11:43]) != authority
            or encode_base58(raw[43:75]) != mint
            or encode_base58(raw[75:107]) != WSOL_MINT):
        raise ValueError("POOL_IDENTITY_MISMATCH")
    return {"base_vault": encode_base58(raw[139:171]),
            "quote_vault": encode_base58(raw[171:203]),
            "lp_supply": struct.unpack_from("<Q", raw, 203)[0],
            "virtual_quote_reserves": (
                int.from_bytes(raw[245:261], "little", signed=True) if len(raw) >= 261 else 0),
            "account_data_len": len(raw),
            "account_data_sha256": hashlib.sha256(raw).hexdigest()}


def decode_token_account(value: dict | None, mint: str, owner: str) -> dict:
    if value is None:
        raise ValueError("TOKEN_ACCOUNT_MISSING")
    token_program = value.get("owner")
    if token_program not in (TOKEN_PROGRAM, TOKEN_2022_PROGRAM):
        raise ValueError("TOKEN_PROGRAM_UNSUPPORTED")
    raw = account_bytes(value, token_program)
    if len(raw) < 165:
        raise ValueError("TOKEN_LAYOUT_MISMATCH")
    if encode_base58(raw[:32]) != mint or encode_base58(raw[32:64]) != owner:
        raise ValueError("TOKEN_MINT_OR_OWNER_MISMATCH")
    return {"amount": struct.unpack_from("<Q", raw, 64)[0],
            "token_program": token_program,
            "account_data_sha256": hashlib.sha256(raw).hexdigest()}


def decode_config(value: dict | None) -> dict:
    raw = account_bytes(value, PUMP_AMM_PROGRAM)
    if len(raw) < 57 or raw[:8] != CONFIG_DISCRIMINATOR:
        raise ValueError("CONFIG_LAYOUT_MISMATCH")
    return {"lp_fee_bps": struct.unpack_from("<Q", raw, 40)[0],
            "protocol_fee_bps": struct.unpack_from("<Q", raw, 48)[0],
            "disable_flags": raw[56],
            "account_data_len": len(raw),
            "account_data_sha256": hashlib.sha256(raw).hexdigest()}


def rpc_values(record: dict, length: int) -> tuple[list | None, int | None]:
    body = record.get("body")
    result = body.get("result") if isinstance(body, dict) else None
    values = result.get("value") if isinstance(result, dict) else None
    context = result.get("context") if isinstance(result, dict) else None
    if (record.get("http_status") != 200 or not isinstance(values, list)
            or len(values) != length or not isinstance(context, dict)
            or not isinstance(context.get("slot"), int)):
        return None, None
    return values, context["slot"]


def timing(record: dict, target_at: str) -> dict:
    target = datetime.fromisoformat(target_at)
    dispatch = datetime.fromisoformat(record["dispatch_at"])
    received = datetime.fromisoformat(record["received_at"])
    return {"dispatch_at": record["dispatch_at"], "received_at": record["received_at"],
            "dispatch_lag_seconds": (dispatch - target).total_seconds(),
            "response_lag_seconds": (received - target).total_seconds()}


def visible_latest_slot(observations: list[dict], mint: str, received_at: str) -> int | None:
    received = datetime.fromisoformat(received_at)
    slots = [row["slot"] for row in observations
             if row.get("mint") == mint and row["event_type"] in (
                 "TradeEvent", "CompleteEvent", "CompletePumpAmmMigrationEvent")
             and datetime.fromisoformat(row["available_at"]) <= received]
    return max(slots) if slots else None


def evaluate(session: Path, companion: Path, direct_path: Path) -> dict:
    audit_path = session / "audit.json"
    audit = json.loads(audit_path.read_text())
    capture_path = session / "capture-manifest.json"
    capture = json.loads(capture_path.read_text())
    manifest_path = companion / "companion-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    direct = json.loads(direct_path.read_text())
    if (manifest["source_capture_manifest_sha256"] != digest(capture_path)
            or manifest["source_segment_sha256"] != capture["segment_sha256"]
            or manifest["pump_amm_idl_sha256"] != digest(AMM_IDL_PATH)
            or direct["audit_sha256"] != digest(audit_path)):
        raise ValueError("source cohort or pinned protocol differs")
    observations = json_lines(session / "observations.jsonl")
    audited_creates = {row["signature"]: row for row in observations
                       if row["event_type"] == "CreateEvent"}
    captured_creates = json_lines(companion / "creates.jsonl")
    selected = json_lines(companion / "selected.jsonl")
    quarantined = {row["signature"] for row in audit.get("quarantined_notifications", [])}
    expected_creates = {(row["signature"], row["mint"]) for row in observations
                        if row["event_type"] == "CreateEvent"}
    actual_creates = {(row["signature"], row["mint"]) for row in captured_creates
                      if row["signature"] not in quarantined}
    create_mismatch = expected_creates != actual_creates
    expected_selected = {signature for signature, row in audited_creates.items()
                         if row["quote_mint"] == NATIVE_QUOTE
                         and not row["is_mayhem_mode"]}
    selected_by_signature = {row["signature"]: row for row in selected
                             if row["signature"] not in quarantined}
    selection_mismatch = (len(selected_by_signature) != len(selected)
                          or set(selected_by_signature) != expected_selected)
    for signature, chosen in selected_by_signature.items():
        original = audited_creates.get(signature)
        authority, pool = canonical_pump_pool(chosen["mint"])
        if (original is None or original["mint"] != chosen["mint"]
                or original["bonding_curve"] != chosen["bonding_curve"]
                or original["available_at"] != chosen["create_received_at"]
                or chosen["pool_authority"] != authority or chosen["pool"] != pool):
            selection_mismatch = True

    first_reads = {}
    read_errors = []
    for path in sorted((companion / "first").glob("*.json")):
        record = json.loads(path.read_text())
        requested = record["requested"]
        expected_addresses = [address for row in requested for address in (
            row["bonding_curve"], row["pool"])] + [AMM_CONFIG]
        if record["addresses"] != expected_addresses:
            read_errors.append(f"FIRST_ADDRESSES_{path.name}")
        values, slot = rpc_values(record, len(expected_addresses))
        for index, item in enumerate(requested):
            signature = item["signature"]
            if signature in first_reads or selected_by_signature.get(signature) != item:
                read_errors.append(f"FIRST_SELECTION_{signature}")
                continue
            first_reads[signature] = {"record": record, "values": values,
                                      "index": index, "slot": slot,
                                      "response_file_sha256": digest(path)}
    second_reads = {}
    for path in sorted((companion / "second").glob("*.json")):
        record = json.loads(path.read_text())
        signature = record["requested"]["signature"]
        if signature in second_reads or selected_by_signature.get(signature) != record["requested"]:
            read_errors.append(f"SECOND_SELECTION_{signature}")
            continue
        second_reads[signature] = {"record": record,
                                   "response_file_sha256": digest(path)}
    missing_first = sorted(set(selected_by_signature) - set(first_reads))
    unexpected_first = sorted(set(first_reads) - set(selected_by_signature))
    unexpected_second = sorted(set(second_reads) - set(selected_by_signature))
    data_gate = (audit["coverage_status"] == "SIGNATURES_MATCH_INNER_SLOTS"
                 and not audit["capture_errors"] and not audit["index_errors"]
                 and audit["successful_transactions_with_truncated_logs"] == 0
                 and audit["event_decode_error_count"] == 0
                 and not audit["event_transaction_identity_mismatches"]
                 and audit["created_mint_trade_state_continuity"]["native_nonmayhem_fail"] == 0
                 and audit["native_nonmayhem_quote_validation"]["fail"] == 0
                 and direct["data_gate_pass"]
                 and manifest["end_reason"] == "capture_finished_and_reads_attempted"
                 and manifest["parsed_frame_count"] == capture["frames"]
                 and manifest["selected_create_count"] == len(selected)
                 and manifest["first_read_count"] == len(selected)
                 and manifest["saved_first_batches"] == len(list((companion / "first").glob(
                     "*.json")))
                 and manifest["saved_second_reads"] == len(second_reads)
                 and manifest["dispatched_second_reads"] == len(second_reads)
                 and not manifest["errors"] and not create_mismatch
                 and not selection_mismatch and not read_errors
                 and not missing_first and not unexpected_first and not unexpected_second)

    direct_rows = {row["signature"]: row for row in direct["rows"]}
    core_start, core_end = audit["inner_slot_bounds"]
    rows = []
    for signature, chosen in sorted(selected_by_signature.items(), key=lambda item: (
            item[1]["create_received_at"], item[0])):
        original = audited_creates[signature]
        direct_row = direct_rows.get(signature, {})
        row = {"signature": signature, "mint": chosen["mint"],
               "create_slot": original["slot"],
               "in_covered_core": core_start <= original["slot"] <= core_end,
               "direct_quote_status": direct_row.get("direct_quote_status"),
               "identity_status": direct_row.get("identity_status"),
               "baseline_status": direct_row.get("baseline_status"),
               "pool": chosen["pool"], "pool_authority": chosen["pool_authority"],
               "status": "ROUTE_READ_MISSING"}
        first = first_reads.get(signature)
        if first is None:
            rows.append(row)
            continue
        first_record = first["record"]
        first_timing = timing(first_record, chosen["target_at"])
        values = first["values"]
        row["first"] = {**first_timing, "context_slot": first["slot"],
                        "response_file_sha256": first["response_file_sha256"]}
        if values is None:
            row["status"] = "RPC_UNAVAILABLE"
            rows.append(row)
            continue
        try:
            first_curve = decode_curve(values[2 * first["index"]])
            decode_config(values[-1])
            if first_curve["quote_mint"] != NATIVE_QUOTE or first_curve["is_mayhem_mode"]:
                raise ValueError("CURVE_REGIME_MISMATCH")
        except (TypeError, ValueError, KeyError) as exc:
            row["status"] = "FIRST_ACCOUNT_UNUSABLE"
            row["reason"] = str(exc)
            rows.append(row)
            continue
        row["first"]["curve_complete"] = first_curve["complete"]
        latest = visible_latest_slot(observations, chosen["mint"], first_timing["received_at"])
        row["first"]["last_visible_mint_slot"] = latest
        first_timely = (0 <= first_timing["dispatch_lag_seconds"] <= 2
                        and 0 <= first_timing["response_lag_seconds"] <= 5)
        first_fresh = first["slot"] >= original["slot"] and (
            latest is None or first["slot"] >= latest)
        row["first"]["timely_and_fresh"] = first_timely and first_fresh
        pool_value = values[2 * first["index"] + 1]
        if not first_timely or not first_fresh:
            row["status"] = "FIRST_READ_LATE_OR_STALE"
        elif pool_value is None:
            row["status"] = "CANONICAL_POOL_ABSENT_AT_SNAPSHOT"
        else:
            try:
                first_pool = decode_pool(pool_value, chosen["mint"], chosen["pool_authority"])
                row["first"]["pool"] = first_pool
                row["status"] = "POOL_PRESENT_INCOMPLETE"
            except (TypeError, ValueError, KeyError) as exc:
                row["status"] = "POOL_PRESENT_UNUSABLE"
                row["reason"] = str(exc)

        second = second_reads.get(signature)
        if second is not None:
            second_record = second["record"]
            second_timing = timing(second_record, chosen["target_at"])
            second_values, second_slot = rpc_values(second_record, 5)
            row["second"] = {**second_timing, "context_slot": second_slot,
                             "response_file_sha256": second["response_file_sha256"]}
            if row["status"] not in ("POOL_PRESENT_INCOMPLETE", "FIRST_READ_LATE_OR_STALE"):
                read_errors.append(f"UNEXPECTED_SECOND_{signature}")
            if second_values is not None:
                try:
                    second_pool = decode_pool(second_values[1], chosen["mint"],
                                              chosen["pool_authority"])
                    expected_addresses = [chosen["bonding_curve"], chosen["pool"],
                                          second_pool["base_vault"],
                                          second_pool["quote_vault"], AMM_CONFIG]
                    if second_record["addresses"] != expected_addresses:
                        raise ValueError("SECOND_ADDRESSES_MISMATCH")
                    second_curve = decode_curve(second_values[0])
                    base = decode_token_account(second_values[2], chosen["mint"],
                                                chosen["pool"])
                    quote = decode_token_account(second_values[3], WSOL_MINT,
                                                 chosen["pool"])
                    config = decode_config(second_values[4])
                    latest_second = visible_latest_slot(observations, chosen["mint"],
                                                         second_timing["received_at"])
                    fresh = second_slot >= original["slot"] and (
                        latest_second is None or second_slot >= latest_second)
                    timely = 0 <= second_timing["response_lag_seconds"] <= 8
                    row["second"].update({"pool": second_pool,
                                          "curve_complete": second_curve["complete"],
                                          "base_vault": base, "quote_vault": quote,
                                          "effective_quote_reserves": (
                                              quote["amount"] + second_pool[
                                                  "virtual_quote_reserves"]),
                                          "config": config,
                                          "last_visible_mint_slot": latest_second,
                                          "timely_and_fresh": timely and fresh})
                    if row["status"] == "POOL_PRESENT_INCOMPLETE" and timely and fresh:
                        row["status"] = "CANONICAL_POOL_VAULTS_DECODED"
                except (TypeError, ValueError, KeyError) as exc:
                    row["second"]["reason"] = str(exc)
        rows.append(row)

    core = [row for row in rows if row["in_covered_core"]]
    groups = {}
    for direct_status in ("QUOTED", "EXIT_UNAVAILABLE", "ENTRY_UNAVAILABLE",
                          "OTHER_OR_UNKNOWN"):
        group = [row for row in core if (row["direct_quote_status"] == direct_status
                 if direct_status != "OTHER_OR_UNKNOWN" else row["direct_quote_status"] not in (
                     "QUOTED", "EXIT_UNAVAILABLE", "ENTRY_UNAVAILABLE"))]
        groups[direct_status] = {"count": len(group), "route_statuses": dict(
            Counter(row["status"] for row in group))}
    first_lags = [row["first"]["response_lag_seconds"] for row in rows if "first" in row]
    second_lags = [row["second"]["response_lag_seconds"] for row in rows if "second" in row]
    return {"schema": "rocket.memecoin.mc017-route-audit.v1",
            "audit_sha256": digest(audit_path),
            "route_manifest_sha256": digest(manifest_path),
            "direct_result_sha256": digest(direct_path),
            "data_gate_pass": data_gate and not read_errors,
            "create_mismatch": create_mismatch,
            "selection_mismatch": selection_mismatch,
            "read_errors": read_errors,
            "missing_first": missing_first,
            "unexpected_first": unexpected_first,
            "unexpected_second": unexpected_second,
            "native_selected_creates": len(rows), "covered_core_creates": len(core),
            "groups": groups,
            "route_status_counts": dict(Counter(row["status"] for row in core)),
            "first_response_lag_seconds": {
                "median": statistics.median(first_lags) if first_lags else None,
                "p90": percentile(first_lags, 0.9)},
            "second_response_lag_seconds": {
                "median": statistics.median(second_lags) if second_lags else None,
                "p90": percentile(second_lags, 0.9)},
            "rows": rows,
            "scope": "Canonical PumpSwap state near exit; no other-venue absence, cash recovery or achieved fill claim."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("companion", type=Path)
    parser.add_argument("direct_result", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.session, args.companion, args.direct_result)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
