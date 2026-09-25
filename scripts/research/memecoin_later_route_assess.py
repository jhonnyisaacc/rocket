"""Classify later pool listings against direct exits and canonical PumpSwap PDAs."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from rocket.research.solana_pda import canonical_pump_pool


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(direct_path: Path, probe_path: Path, response_dir: Path) -> dict:
    direct = json.loads(direct_path.read_text())
    probe = json.loads(probe_path.read_text())
    direct_by_mint = {row["mint"]: row for row in direct["rows"]}
    if len(direct_by_mint) != len(direct["rows"]):
        raise ValueError("duplicate direct mint")
    response_paths = sorted(response_dir.glob("batch-*.json"))
    if len(response_paths) != len(probe["response_hashes"]):
        raise ValueError("incomplete saved response set")
    response_hashes = {path.name: sha(path) for path in response_paths}
    for record in probe["response_hashes"]:
        name = f"batch-{record['batch']:03d}.json"
        if response_hashes.get(name) != record["sha256"]:
            raise ValueError(f"response digest mismatch: {name}")
    request_times = []
    for path in response_paths:
        record = json.loads(path.read_text())
        successes = [item for item in record["attempts"] if item.get("http_status") == 200
                     and isinstance(item.get("body"), list)]
        if not successes:
            raise ValueError(f"no usable response: {path.name}")
        request_times.append((successes[-1]["requested_at"], successes[-1]["received_at"]))
    rows = []
    for row in probe["rows"]:
        mint = row["mint"]
        direct_row = direct_by_mint[mint]
        if row["group"] == "curve_unavailable" and direct_row[
                "direct_quote_status"] != "EXIT_UNAVAILABLE":
            raise ValueError(f"baseline/direct exit disagreement: {mint}")
        _, canonical = canonical_pump_pool(mint)
        pairs = []
        for pair in row["pairs"]:
            address = pair["pair_address"]
            if address == canonical:
                kind = "CANONICAL_PUMPSWAP"
            elif pair["dex_id"] == "pumpfun":
                kind = "PUMP_CURVE_LISTING"
            else:
                kind = "OTHER_POOL_LEAD"
            pairs.append({**pair, "route_kind": kind})
        rows.append({"mint": mint, "group": row["group"],
                     "direct_quote_status": direct_row["direct_quote_status"],
                     "frozen_exit_at": row["frozen_exit_at"], "pairs": pairs})
    groups = {}
    for group in ("curve_unavailable", "quoted_control"):
        subset = [row for row in rows if row["group"] == group]
        groups[group] = {"selected": len(subset),
                         "direct_status_counts": dict(Counter(
                             row["direct_quote_status"] for row in subset)),
                         "listed_pump_curve": sum(any(pair["route_kind"] ==
                             "PUMP_CURVE_LISTING" for pair in row["pairs"])
                             for row in subset),
                         "listed_canonical_pumpswap": sum(any(pair["route_kind"] ==
                             "CANONICAL_PUMPSWAP" for pair in row["pairs"])
                             for row in subset),
                         "listed_other_pool_lead": sum(any(pair["route_kind"] ==
                             "OTHER_POOL_LEAD" for pair in row["pairs"])
                             for row in subset)}
    if any(datetime.fromisoformat(start) <= datetime.fromisoformat(
            row["frozen_exit_at"]) for start, _ in request_times for row in rows):
        raise ValueError("later probe was not uniformly later")
    return {"schema": "rocket.memecoin.mc018-later-route-assessment.v1",
            "direct_sha256": sha(direct_path), "probe_sha256": sha(probe_path),
            "response_hashes": response_hashes,
            "first_request_at": min(start for start, _ in request_times),
            "last_response_at": max(end for _, end in request_times),
            "groups": groups, "rows": rows,
            "scope": "Third-party listings collected after every exit; no as-of route or cash quote."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("direct", type=Path)
    parser.add_argument("probe", type=Path)
    parser.add_argument("responses", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = assess(args.direct, args.probe, args.responses)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "first_request_at", "last_response_at", "groups")}, indent=2))
