"""Offline MC-023 stratified unsigned entry and +67s canonical-route audit."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import statistics
from datetime import datetime
from pathlib import Path

from scripts.research.memecoin_curve_snapshot_audit import decode_curve
from scripts.research.memecoin_route_snapshot_audit import (
    decode_pool,
    decode_token_account,
    rpc_values,
    timing,
    visible_latest_slot,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seconds(after: str, before: str) -> float:
    return (datetime.fromisoformat(after) - datetime.fromisoformat(before)).total_seconds()


def token_amount(account: dict | None) -> int | None:
    if account is None:
        return None
    raw = base64.b64decode(account["data"][0])
    return int.from_bytes(raw[64:72], "little")


def read_route_first(route: Path) -> dict[str, tuple[dict, int]]:
    found = {}
    for file in sorted((route / "first").glob("batch-*.json")):
        response = json.loads(file.read_text())
        for index, row in enumerate(response["requested"]):
            signature = row["signature"]
            if signature in found:
                raise ValueError(f"duplicate first route read: {signature}")
            found[signature] = (response, index)
    return found


def route_state(chosen: dict, first: tuple[dict, int] | None, route: Path,
                observations: list[dict], base_amount: int | None) -> dict:
    if first is None:
        return {"status": "ROUTE_READ_MISSING"}
    record, index = first
    clock = timing(record, chosen["target_at"])
    values, slot = rpc_values(record, 2 * len(record["requested"]) + 1)
    result = {"status": "ROUTE_RPC_UNAVAILABLE", "dispatch_lag_s": clock["dispatch_lag_seconds"],
              "response_lag_s": clock["response_lag_seconds"], "bank_slot": slot}
    if values is None:
        return result
    latest = visible_latest_slot(observations, chosen["mint"], record["received_at"])
    timely = (0 <= clock["dispatch_lag_seconds"] <= 2
              and 0 <= clock["response_lag_seconds"] <= 5)
    fresh = slot >= chosen["slot"] and (latest is None or slot >= latest)
    result.update({"timely": timely, "fresh": fresh,
                   "last_visible_mint_slot": latest})
    if not timely or not fresh:
        result["status"] = "ROUTE_LATE_OR_STALE"
        return result
    try:
        curve = decode_curve(values[2 * index])
        if curve["is_mayhem_mode"] or curve["quote_mint"] not in (
                "11111111111111111111111111111111",
                "So11111111111111111111111111111111111111112"):
            raise ValueError("selected native non-Mayhem curve changed")
        result["curve"] = curve
        result["status"] = "CURVE_DECODED"
        if base_amount is not None and curve["virtual_token_reserves"] > 0:
            gross = (base_amount * curve["virtual_quote_reserves"]
                     // (curve["virtual_token_reserves"] + base_amount))
            result["gross_sell_quote_lamports_before_fees"] = gross
            result["direct_curve_liquidity_available"] = (
                gross > 0 and gross <= curve["real_quote_reserves"])
    except (TypeError, ValueError, KeyError) as exc:
        result.update({"status": "CURVE_UNUSABLE", "reason": str(exc)})
        return result
    pool_value = values[2 * index + 1]
    if pool_value is None:
        result["canonical_pool_present"] = False
        return result
    try:
        pool = decode_pool(pool_value, chosen["mint"], chosen["pool_authority"])
        result["canonical_pool_present"] = True
        result["pool"] = pool
    except (TypeError, ValueError, KeyError) as exc:
        result.update({"canonical_pool_present": None, "pool_error": str(exc)})
        return result
    second_file = route / "second" / f"{chosen['signature']}.json"
    if not second_file.exists():
        result["pool_vault_state"] = "SECOND_READ_MISSING"
        return result
    second = json.loads(second_file.read_text())
    second_values, second_slot = rpc_values(second, 5)
    second_clock = timing(second, chosen["target_at"])
    second_latest = visible_latest_slot(observations, chosen["mint"], second["received_at"])
    result["second_response_lag_s"] = second_clock["response_lag_seconds"]
    result["second_bank_slot"] = second_slot
    result["second_last_visible_mint_slot"] = second_latest
    if (second_values is None or second_clock["response_lag_seconds"] < 0
            or second_clock["response_lag_seconds"] > 8
            or second_slot < chosen["slot"]
            or (second_latest is not None and second_slot < second_latest)):
        result["pool_vault_state"] = "SECOND_READ_UNUSABLE"
        return result
    try:
        second_pool = decode_pool(second_values[1], chosen["mint"], chosen["pool_authority"])
        if second_pool["base_vault"] != pool["base_vault"] or (
                second_pool["quote_vault"] != pool["quote_vault"]):
            raise ValueError("pool vault address changed")
        base = decode_token_account(second_values[2], chosen["mint"], chosen["pool"])
        quote = decode_token_account(second_values[3],
                                     "So11111111111111111111111111111111111111112",
                                     chosen["pool"])
        result["pool_vault_state"] = "VAULTS_DECODED"
        result["pool_base_amount"] = base["amount"]
        result["pool_quote_amount"] = quote["amount"]
    except (TypeError, ValueError, KeyError) as exc:
        result["pool_vault_state"] = "VAULTS_UNUSABLE"
        result["vault_error"] = str(exc)
    return result


def audit(session: Path, entry: Path, route: Path) -> dict:
    capture = json.loads((session / "capture-manifest.json").read_text())
    primary = json.loads((session / "audit.json").read_text())
    selection = json.loads((entry / "selection.json").read_text())
    identity = json.loads((entry / "signed-identities.json").read_text())
    route_manifest = json.loads((route / "companion-manifest.json").read_text())
    assert capture["requested_seconds"] == 300
    assert digest(session / capture["segment"]) == capture["segment_sha256"]
    assert selection["schema"] == "rocket.memecoin.mc023-selection.v1"
    assert route_manifest["source_segment_sha256"] == capture["segment_sha256"]
    assert route_manifest["parsed_frame_count"] == capture["frames"]
    assert identity["selection_sha256"] == digest(entry / "selection.json")
    chosen = selection["selected"]
    assert chosen == [row for row in selection["creates"]
                      if row["selection_status"] == "SELECTED"]
    assert [row["selection_index"] for row in chosen] == list(range(len(chosen)))
    assert len(chosen) <= 20 and selection["bucket_counts"] == [
        sum(row["bucket"] == bucket for row in chosen) for bucket in range(5)]
    for row in chosen:
        position = row["bucket_position"]
        assert 0 <= row["bucket"] < 5 and 0 <= position < 4
        assert row["target_delay_seconds"] == (5, 5, 8, 8)[position]
        assert row["budget_lamports"] == (10000000, 50000000,
                                          10000000, 50000000)[position]
    signed = {row["signature"]: row for row in identity["rows"]}
    assert set(signed) == {row["signature"] for row in chosen}
    routes = {json.loads(line)["signature"]: json.loads(line)
              for line in (route / "selected.jsonl").read_text().splitlines()}
    first_reads = read_route_first(route)
    observations = [json.loads(line) for line in
                    (session / "observations.jsonl").read_text().splitlines()]
    rows = []
    for row in chosen:
        item = {"signature": row["signature"], "mint": row["mint"],
                "bucket": row["bucket"], "bucket_position": row["bucket_position"],
                "target_delay_seconds": row["target_delay_seconds"],
                "budget_lamports": row["budget_lamports"],
                "identity_status": signed[row["signature"]]["status"],
                "covered_interior": primary["inner_slot_bounds"][0] <= row["slot"]
                <= primary["inner_slot_bounds"][1]}
        if item["identity_status"] == "STRICT_IDENTITY":
            decoded = signed[row["signature"]]["decoded"]
            assert decoded["mint"] == row["mint"] and decoded["slot"] == row["slot"]
        path = entry / f"simulation-{row['selection_index']:02d}.json"
        base_amount = None
        if not path.exists():
            item["entry_status"] = "SIMULATION_FILE_MISSING"
        else:
            sim = json.loads(path.read_text())
            assert sim["schema"] == "rocket.memecoin.mc023-unsigned-buy.v1"
            assert sim["mint"] == row["mint"]
            assert int(sim["budgetLamports"]) == row["budget_lamports"]
            assert int(sim["maxSpendLamports"]) == row["budget_lamports"] * 101 // 100
            if "unsignedTransactionBase64" in sim:
                transaction = base64.b64decode(sim["unsignedTransactionBase64"])
                assert transaction[0] == 1 and transaction[1:65] == bytes(64)
                assert hashlib.sha256(transaction).hexdigest() == sim[
                    "unsignedTransactionSha256"]
            calls = sim["calls"]
            item["first_dispatch_after_receipt_s"] = seconds(
                calls[0]["dispatchAt"], row["create_received_at"])
            item["bank_slot"] = sim.get("bankSlot")
            item["quoted_base_amount"] = sim.get("quote", {}).get("quotedBaseAmount")
            item["requested_base_amount"] = sim.get("quote", {}).get("requestedBaseAmount")
            item["fatal_error"] = sim.get("fatalError")
            if len(calls) > 1:
                item["bank_request_after_receipt_s"] = seconds(
                    calls[1]["dispatchAt"], row["create_received_at"])
            last = calls[-1]
            if last["request"]["method"] == "simulateTransaction" and (
                    last.get("response", {}).get("result")):
                value = last["response"]["result"]["value"]
                item["simulation_response_after_receipt_s"] = seconds(
                    last["receivedAt"], row["create_received_at"])
                item["simulation_slot"] = last["response"]["result"]["context"]["slot"]
                item["simulation_error"] = value["err"]
                item["units_consumed"] = value.get("unitsConsumed")
                item["simulated_network_fee_lamports"] = value.get("fee")
                item["on_time"] = (
                    item.get("bank_request_after_receipt_s", 1e9)
                    <= row["target_delay_seconds"] + 3
                    and item["simulation_response_after_receipt_s"]
                    <= row["target_delay_seconds"] + 7)
                item["entry_status"] = (
                    "SIMULATION_SUCCESS" if value["err"] is None else "SIMULATION_ERROR")
                if value["err"] is None and value.get("accounts"):
                    owner, base_ata, _ = value["accounts"]
                    before = sim["bankState"]
                    base_amount = token_amount(base_ata) - int(before["userBaseAmount"] or 0)
                    item["simulated_base_delta"] = base_amount
                    item["simulated_owner_native_delta_lamports"] = (
                        owner["lamports"] - before["userLamports"])
                    assert base_amount == int(item["requested_base_amount"])
            else:
                item["entry_status"] = "BUILD_OR_RPC_ERROR"
        route_row = routes.get(row["signature"])
        if route_row is None:
            item["route"] = {"status": "ROUTE_SELECTION_MISSING"}
        else:
            assert route_row["mint"] == row["mint"]
            item["route"] = route_state(route_row, first_reads.get(row["signature"]),
                                        route, observations, base_amount)
        rows.append(item)
    cells = {}
    for position in range(4):
        subset = [item for item in rows if item["bucket_position"] == position]
        cells[str(position)] = {"selected": len(subset),
                                "simulated": sum(item["entry_status"].startswith("SIMULATION_")
                                                 for item in subset),
                                "success": sum(item["entry_status"] == "SIMULATION_SUCCESS"
                                               for item in subset),
                                "on_time_success": sum(item["entry_status"] == "SIMULATION_SUCCESS"
                                                       and item.get("on_time", False)
                                                       for item in subset)}
    latencies = [item["simulation_response_after_receipt_s"] for item in rows
                 if "simulation_response_after_receipt_s" in item]
    return {"schema": "rocket.memecoin.mc023-entry-route-audit.v1",
            "capture_end_reason": capture["end_reason"], "capture_errors": capture["errors"],
            "coverage_status": primary["coverage_status"],
            "inner_stream_signatures": primary["inner_stream_signatures"],
            "inner_index_signatures": primary["inner_index_signatures"],
            "missing_from_stream_count": primary["missing_from_stream_count"],
            "missing_from_index_count": primary["missing_from_index_count"],
            "event_decode_error_count": primary["event_decode_error_count"],
            "truncated_log_count": primary["successful_transactions_with_truncated_logs"],
            "quarantined_notification_count": primary["quarantined_notification_count"],
            "route_companion_end_reason": route_manifest["end_reason"],
            "route_companion_errors": route_manifest["errors"],
            "all_decoded_creates": len(selection["creates"]),
            "selected_count": len(rows), "bucket_counts": selection["bucket_counts"],
            "signed_identity_count": sum(item["identity_status"] == "STRICT_IDENTITY"
                                         for item in rows),
            "covered_interior_count": sum(item["covered_interior"] for item in rows),
            "simulation_success_count": sum(item["entry_status"] == "SIMULATION_SUCCESS"
                                            for item in rows),
            "on_time_success_count": sum(item["entry_status"] == "SIMULATION_SUCCESS"
                                         and item.get("on_time", False) for item in rows),
            "direct_curve_available_count": sum(item["route"].get(
                "direct_curve_liquidity_available") is True for item in rows
                if item["entry_status"] == "SIMULATION_SUCCESS"),
            "response_latency_median_s": statistics.median(latencies) if latencies else None,
            "cells": cells, "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("entry", type=Path)
    parser.add_argument("route", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit(args.session, args.entry, args.route)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text)
    print(text, end="")
