"""Offline MC-022 selection and unsigned Pump buy simulation audit."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import statistics
from datetime import datetime
from pathlib import Path


def token_amount(account: dict | None) -> int | None:
    if account is None:
        return None
    data = base64.b64decode(account["data"][0])
    return int.from_bytes(data[64:72], "little")


def seconds(after: str, before: str) -> float:
    return (datetime.fromisoformat(after) - datetime.fromisoformat(before)).total_seconds()


def audit(session: Path, companion: Path) -> dict:
    capture = json.loads((session / "capture-manifest.json").read_text())
    index = json.loads((session / "audit.json").read_text())
    selection = json.loads((companion / "selection.json").read_text())
    identity = json.loads((companion / "signed-identities.json").read_text())
    rows = selection["creates"]
    chosen = selection["selected"]
    assert capture["segment_sha256"] == hashlib.sha256(
        (session / capture["segment"]).read_bytes()).hexdigest()
    assert capture["requested_seconds"] == 180
    assert len(chosen) <= 5
    assert chosen == [row for row in rows if row["selection_status"] == "SELECTED"]
    assert len({row["signature"] for row in rows}) == len(rows)
    assert [row["selection_index"] for row in chosen] == list(range(len(chosen)))
    assert identity["selection_sha256"] == hashlib.sha256(
        (companion / "selection.json").read_bytes()).hexdigest()
    identities = {row["signature"]: row for row in identity["rows"]}
    assert len(identities) == len(chosen)
    assert all(row["quote_mint"] in (None, "11111111111111111111111111111111",
                                      "So11111111111111111111111111111111111111112")
               and row["is_mayhem_mode"] is False for row in chosen)
    results = []
    for row in chosen:
        file = companion / f"simulation-{row['selection_index']:02d}.json"
        item = {"mint": row["mint"], "create_signature": row["signature"],
                "create_slot": row["slot"], "create_received_at": row["create_received_at"],
                "target_at": row["target_at"], "selected_subprocess_exit": row.get("exit_code")}
        item["signed_identity_status"] = identities[row["signature"]]["status"]
        if item["signed_identity_status"] == "STRICT_IDENTITY":
            signed = identities[row["signature"]]["decoded"]
            assert signed["mint"] == row["mint"] and signed["slot"] == row["slot"]
        item["interior_slot"] = (index["inner_slot_bounds"][0] <= row["slot"]
                                 <= index["inner_slot_bounds"][1])
        if not file.exists():
            item["status"] = "NO_SIMULATION_FILE"
            results.append(item)
            continue
        sim = json.loads(file.read_text())
        assert sim["schema"] == "rocket.memecoin.mc022-unsigned-buy.v1"
        assert sim["mint"] == row["mint"]
        assert sim["budgetLamports"] == "10000000"
        assert sim["maxSpendLamports"] == "10100000"
        assert sim["computeLimit"] == 400000
        assert sim["computeUnitPriceMicroLamports"] == 100000
        calls = sim["calls"]
        assert calls[0]["request"]["method"] == "getMultipleAccounts"
        item["first_rpc_dispatch_after_receive_s"] = seconds(
            calls[0]["dispatchAt"], row["create_received_at"])
        if len(calls) > 1:
            item["bank_request_after_receive_s"] = seconds(
                calls[1]["dispatchAt"], row["create_received_at"])
        item["bank_slot"] = sim.get("bankSlot")
        if "bankSlot" in sim:
            assert sim["bankSlot"] >= row["slot"]
            assert sim["bankState"]["curve"] == row["bonding_curve"]
        if "unsignedTransactionBase64" in sim:
            data = base64.b64decode(sim["unsignedTransactionBase64"])
            assert data[0] == 1 and data[1:65] == bytes(64)
            assert hashlib.sha256(data).hexdigest() == sim["unsignedTransactionSha256"]
        item["quoted_base_raw"] = sim.get("quote", {}).get("quotedBaseAmount")
        item["requested_base_raw"] = sim.get("quote", {}).get("requestedBaseAmount")
        item["fatal_error"] = sim.get("fatalError")
        last = calls[-1]
        item["last_rpc_method"] = last["request"]["method"]
        item["last_rpc_http_status"] = last.get("httpStatus")
        if last["request"]["method"] == "simulateTransaction" and last.get("response", {}).get("result"):
            result = last["response"]["result"]
            value = result["value"]
            item["simulation_response_after_receive_s"] = seconds(
                last["receivedAt"], row["create_received_at"])
            item["simulation_slot"] = result["context"]["slot"]
            item["simulation_err"] = value["err"]
            item["units_consumed"] = value.get("unitsConsumed")
            item["simulated_fee_lamports"] = value.get("fee")
            item["on_time"] = (item.get("bank_request_after_receive_s", 1e9) <= 8
                               and item["simulation_response_after_receive_s"] <= 12)
            if value["err"] is None and value.get("accounts"):
                owner, base_ata, _ = value["accounts"]
                before = sim["bankState"]
                item["simulated_owner_native_delta_lamports"] = (
                    owner["lamports"] - before["userLamports"])
                before_base = int(before["userBaseAmount"] or 0)
                item["simulated_base_delta_raw"] = token_amount(base_ata) - before_base
                assert item["simulated_base_delta_raw"] == int(item["requested_base_raw"])
            item["status"] = "SIMULATED_SUCCESS" if value["err"] is None else "SIMULATED_ERROR"
        else:
            item["status"] = "BUILD_OR_RPC_ERROR"
        results.append(item)
    latencies = [item["simulation_response_after_receive_s"] for item in results
                 if "simulation_response_after_receive_s" in item]
    return {"schema": "rocket.memecoin.mc022-audit.v1",
            "capture_end_reason": capture["end_reason"],
            "capture_errors": capture["errors"],
            "coverage_status": index["coverage_status"],
            "event_decode_error_count": index["event_decode_error_count"],
            "truncated_log_count": index["successful_transactions_with_truncated_logs"],
            "quarantined_notification_count": index["quarantined_notification_count"],
            "inner_stream_signatures": index["inner_stream_signatures"],
            "inner_index_signatures": index["inner_index_signatures"],
            "missing_from_stream_count": index["missing_from_stream_count"],
            "missing_from_index_count": index["missing_from_index_count"],
            "decoded_create_count": len(rows),
            "selected_count": len(chosen),
            "strict_selected_identity_count": sum(item["signed_identity_status"] == "STRICT_IDENTITY"
                                                  for item in results),
            "selected_interior_slot_count": sum(item["interior_slot"] for item in results),
            "simulation_attempt_count": sum(item["last_rpc_method"] == "simulateTransaction"
                                            for item in results if "last_rpc_method" in item),
            "simulation_success_count": sum(item["status"] == "SIMULATED_SUCCESS"
                                            for item in results),
            "on_time_success_count": sum(item["status"] == "SIMULATED_SUCCESS"
                                         and item.get("on_time", False) for item in results),
            "simulation_response_latency_median_s": statistics.median(latencies) if latencies else None,
            "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("companion", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit(args.session, args.companion)
    report = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(report)
    print(report, end="")
