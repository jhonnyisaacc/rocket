"""Compare simultaneous bounded Pump websocket sessions on paired signatures."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from datetime import datetime
from pathlib import Path

from rocket.capture.spool import replay_segment


def percentile(values: list[float], fraction: float) -> float | None:
    return sorted(values)[int((len(values) - 1) * fraction)] if values else None


def summary(values: list[float]) -> dict:
    return {"n": len(values), "median": statistics.median(values) if values else None,
            "p90": percentile(values, 0.9), "p99": percentile(values, 0.99),
            "min": min(values) if values else None, "max": max(values) if values else None}


def received_signatures(session: Path, lower_slot: int, upper_slot: int) -> dict[str, dict]:
    manifest = json.loads((session / "capture-manifest.json").read_text())
    rows = {}
    for raw, received_at, _ in replay_segment(session / manifest["segment"]):
        message = json.loads(raw)
        if message.get("method") != "logsNotification":
            continue
        result = message["params"]["result"]
        slot = result["context"]["slot"]
        if lower_slot <= slot <= upper_slot:
            signature = result["value"]["signature"]
            if signature in rows and rows[signature]["slot"] != slot:
                raise ValueError("conflicting notification slot")
            rows.setdefault(signature, {"slot": slot, "received_at": received_at.isoformat()})
    return rows


def create_lags(session: Path, lower_slot: int, upper_slot: int) -> list[float]:
    return [(datetime.fromisoformat(row["available_at"]) -
             datetime.fromisoformat(row["event_time"])).total_seconds()
            for line in (session / "observations.jsonl").read_text().splitlines()
            if (row := json.loads(line))["event_type"] == "CreateEvent"
            and lower_slot <= row["slot"] <= upper_slot]


def compare(beta: Path, mainnet: Path) -> dict:
    beta_audit = json.loads((beta / "audit.json").read_text())
    main_audit = json.loads((mainnet / "audit.json").read_text())
    beta_manifest = json.loads((beta / "capture-manifest.json").read_text())
    main_manifest = json.loads((mainnet / "capture-manifest.json").read_text())
    low = max(beta_audit["inner_slot_bounds"][0], main_audit["inner_slot_bounds"][0])
    high = min(beta_audit["inner_slot_bounds"][1], main_audit["inner_slot_bounds"][1])
    if low > high:
        raise ValueError("no overlapping verified interior slots")
    beta_rows = received_signatures(beta, low, high)
    main_rows = received_signatures(mainnet, low, high)
    common = set(beta_rows) & set(main_rows)
    slot_mismatches = sorted(sig for sig in common
                             if beta_rows[sig]["slot"] != main_rows[sig]["slot"])
    paired = [(datetime.fromisoformat(main_rows[sig]["received_at"]) -
               datetime.fromisoformat(beta_rows[sig]["received_at"])).total_seconds()
              for sig in common if sig not in slot_mismatches]
    beta_lags = create_lags(beta, low, high)
    main_lags = create_lags(mainnet, low, high)
    beta_ok = beta_audit["coverage_status"] == "SIGNATURES_MATCH_INNER_SLOTS"
    main_ok = main_audit["coverage_status"] == "SIGNATURES_MATCH_INNER_SLOTS"
    return {"schema": "rocket.memecoin.mc007-ws-compare.v1",
            "beta_capture_sha256": hashlib.sha256((beta / "capture-manifest.json").read_bytes()).hexdigest(),
            "mainnet_capture_sha256": hashlib.sha256((mainnet / "capture-manifest.json").read_bytes()).hexdigest(),
            "beta_audit_sha256": hashlib.sha256((beta / "audit.json").read_bytes()).hexdigest(),
            "mainnet_audit_sha256": hashlib.sha256((mainnet / "audit.json").read_bytes()).hexdigest(),
            "overlap_inner_slot_bounds": [low, high],
            "beta_coverage": beta_audit["coverage_status"],
            "mainnet_coverage": main_audit["coverage_status"],
            "beta_signatures": len(beta_rows), "mainnet_signatures": len(main_rows),
            "paired_signatures": len(paired),
            "beta_capture_errors": beta_manifest["errors"],
            "mainnet_capture_errors": main_manifest["errors"],
            "missing_from_beta_count": len(set(main_rows) - set(beta_rows)),
            "missing_from_mainnet_count": len(set(beta_rows) - set(main_rows)),
            "slot_mismatch_count": len(slot_mismatches),
            "paired_mainnet_minus_beta_receipt_seconds": summary(paired),
            "mainnet_slower_by_over_5_seconds": sum(value > 5 for value in paired),
            "beta_slower_by_over_5_seconds": sum(value < -5 for value in paired),
            "mainnet_slower_by_over_5_seconds_fraction":
            sum(value > 5 for value in paired) / len(paired) if paired else None,
            "beta_slower_by_over_5_seconds_fraction":
            sum(value < -5 for value in paired) / len(paired) if paired else None,
            "beta_create_age_seconds": summary(beta_lags),
            "mainnet_create_age_seconds": summary(main_lags),
            "beta_whole_second_block_to_receipt_seconds": beta_audit["block_timestamp_to_receive_seconds"],
            "mainnet_whole_second_block_to_receipt_seconds": main_audit[
                "block_timestamp_to_receive_seconds"],
            "beta_eligible_for_longer_test": beta_ok and not beta_manifest["errors"]
            and percentile(beta_lags, 0.9) is not None
            and percentile(beta_lags, 0.9) <= 5 and not slot_mismatches,
            "mainnet_eligible_for_longer_test": main_ok and not main_manifest["errors"]
            and percentile(main_lags, 0.9) is not None
            and percentile(main_lags, 0.9) <= 5 and not slot_mismatches}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("beta", type=Path)
    parser.add_argument("mainnet", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.beta, args.mainnet)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
