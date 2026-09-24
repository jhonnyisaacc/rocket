"""Frozen MC-011 signed-transaction check of early Pump event participants."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx

from scripts.research.memecoin_flow_diagnostics import exact_binomial_interval, percentile
from scripts.research.memecoin_tx_accounting import PUMP_PROGRAM
from scripts.research.memecoin_user_owner_audit import event_sized_account_owner

RPC = "https://solana-rpc.publicnode.com"
TARGETS = {"top_buy": 48, "rest_buy": 48, "top_sell": 24, "rest_sell": 24}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def select(session: Path) -> dict:
    fast_path = session / "mc010-fast-flow-rows.jsonl"
    observations_path = session / "observations.jsonl"
    fast = [json.loads(line) for line in fast_path.read_text().splitlines()]
    top = set()
    for split in ("development", "evaluation"):
        ranked = sorted((row for row in fast if row["split"] == split),
                        key=lambda row: (-row["flow_score"], row["signature"]))
        top.update(row["mint"] for row in ranked[:math.ceil(len(ranked) / 4)])
    start = {row["mint"]: datetime.fromisoformat(row["create_received_at"]) for row in fast}
    all_trades: dict[str, list[dict]] = defaultdict(list)
    early_signatures = set()
    for line in observations_path.read_text().splitlines():
        row = json.loads(line)
        if row["event_type"] != "TradeEvent":
            continue
        all_trades[row["signature"]].append(row)
        t0 = start.get(row["mint"])
        if t0 is not None and t0 <= datetime.fromisoformat(row["available_at"]) <= (
                t0 + timedelta(seconds=5)):
            early_signatures.add(row["signature"])
    strata: dict[str, list[dict]] = defaultdict(list)
    excluded_multi = 0
    for signature in early_signatures:
        events = all_trades[signature]
        if len(events) != 1:
            excluded_multi += 1
            continue
        event = events[0]
        group = "top" if event["mint"] in top else "rest"
        side = "buy" if event["is_buy"] else "sell"
        strata[f"{group}_{side}"].append(event)
    selected = []
    for name, target in TARGETS.items():
        candidates = sorted(strata[name], key=lambda row: (
            digest(f"mc011:{row['signature']}".encode()), row["signature"]))
        for row in candidates[:target]:
            selected.append({"stratum": name, "signature": row["signature"],
                             "slot": row["slot"], "mint": row["mint"],
                             "event_user": row["user"], "event_token_amount": row["token_amount"],
                             "is_buy": row["is_buy"], "event_received_at": row["available_at"],
                             "event_source_hash": row["source_hash"]})
    return {"schema": "rocket.memecoin.mc011-selection.v1",
            "observations_sha256": digest(observations_path.read_bytes()),
            "fast_rows_sha256": digest(fast_path.read_bytes()),
            "method": "sha256('mc011:' + signature) ascending within stratum",
            "target": TARGETS, "fast_verified_mints": len(start),
            "early_unique_trade_signatures": len(early_signatures),
            "excluded_multi_trade_signatures": excluded_multi,
            "population": {name: len(strata[name]) for name in TARGETS},
            "selected": selected}


def fetch(selection_path: Path, response_dir: Path, pace: float, rpc_url: str) -> None:
    selection = json.loads(selection_path.read_text())
    response_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=20) as client:
        for chosen in selection["selected"]:
            signature = chosen["signature"]
            path = response_dir / f"{signature}.json"
            attempts = json.loads(path.read_text())["attempts"] if path.exists() else []
            if any(item.get("body", {}).get("result") for item in attempts):
                continue
            for number in range(1, 4):
                requested_at = datetime.now(UTC).isoformat()
                try:
                    response = client.post(rpc_url, json={
                        "jsonrpc": "2.0", "id": 1, "method": "getTransaction",
                        "params": [signature, {"encoding": "jsonParsed", "commitment": "confirmed",
                                               "maxSupportedTransactionVersion": 1}],
                    })
                    item = {"requested_at": requested_at,
                            "received_at": datetime.now(UTC).isoformat(),
                            "http_status": response.status_code, "body": response.json()}
                except (httpx.HTTPError, ValueError) as exc:
                    item = {"requested_at": requested_at,
                            "received_at": datetime.now(UTC).isoformat(),
                            "error": type(exc).__name__}
                attempts.append(item)
                path.write_text(json.dumps({"signature": signature,
                                            "rpc_host": urlparse(rpc_url).hostname,
                                            "attempts": attempts}, sort_keys=True) + "\n")
                if item.get("body", {}).get("result"):
                    break
                time.sleep(pace * number)
            time.sleep(pace)


def report(session: Path, selection_path: Path, response_dir: Path) -> dict:
    selection = json.loads(selection_path.read_text())
    if selection != select(session):
        raise ValueError("selection differs from frozen source")
    rows = []
    for chosen in selection["selected"]:
        path = response_dir / f"{chosen['signature']}.json"
        row = {**chosen, "response_sha256": digest(path.read_bytes()) if path.exists() else None}
        if not path.exists():
            rows.append({**row, "status": "NOT_FETCHED"})
            continue
        record = json.loads(path.read_text())
        successful = next((item for item in reversed(record["attempts"])
                           if item.get("body", {}).get("result")), None)
        if successful is None:
            rows.append({**row, "status": "UNAVAILABLE", "attempts": len(record["attempts"])})
            continue
        tx = successful["body"]["result"]
        if (chosen["signature"] not in tx["transaction"]["signatures"]
                or chosen["slot"] != tx["slot"]):
            rows.append({**row, "status": "IDENTITY_MISMATCH"})
            continue
        meta = tx.get("meta")
        if not isinstance(meta, dict) or meta.get("err") is not None:
            rows.append({**row, "status": "FAILED_TRANSACTION"})
            continue
        owner = event_sized_account_owner(
            meta, chosen["mint"], chosen["event_token_amount"] *
            (1 if chosen["is_buy"] else -1))
        keys = tx["transaction"]["message"]["accountKeys"]
        signer_keys = {item["pubkey"] for item in keys if item.get("signer")}
        instructions = tx["transaction"]["message"]["instructions"]
        rows.append({**row, "status": "OWNER_IDENTIFIED" if owner else "AMBIGUOUS_OWNER",
                     "token_account_owner": owner, "event_user_matches_owner": (
                         chosen["event_user"] == owner if owner else None),
                     "fee_payer": keys[0]["pubkey"],
                     "fee_payer_matches_owner": keys[0]["pubkey"] == owner if owner else None,
                     "owner_is_signer": owner in signer_keys if owner else None,
                     "top_level_pump": any(item.get("programId") == PUMP_PROGRAM
                                           for item in instructions),
                     "fee_lamports": meta["fee"],
                     "retrieved_at": successful["received_at"],
                     "attempts": len(record["attempts"])})
    strata = {}
    for name in TARGETS:
        group = [row for row in rows if row["stratum"] == name]
        identified = [row for row in group if row["status"] == "OWNER_IDENTIFIED"]
        matches = sum(row["event_user_matches_owner"] for row in identified)
        fees = [row["fee_lamports"] for row in group if "fee_lamports" in row]
        strata[name] = {"population": selection["population"][name], "selected": len(group),
                        "status_counts": dict(Counter(row["status"] for row in group)),
                        "owner_identified": len(identified), "event_user_owner_matches": matches,
                        "event_user_owner_mismatches": len(identified) - matches,
                        "match_exact_95_interval": exact_binomial_interval(matches, len(identified)),
                        "top_level_pump": sum(row.get("top_level_pump", False) for row in group),
                        "routed_top_level": sum(row.get("top_level_pump") is False for row in group),
                        "owner_fee_payer_matches": sum(row["fee_payer_matches_owner"]
                                                       for row in identified),
                        "owner_signer_matches": sum(row["owner_is_signer"]
                                                    for row in identified),
                        "fee_lamports_median": statistics.median(fees) if fees else None,
                        "fee_lamports_p90": percentile(fees, 0.9)}
    return {"schema": "rocket.memecoin.mc011-actor-audit.v1",
            "selection_sha256": digest(selection_path.read_bytes()),
            "selection": {key: value for key, value in selection.items() if key != "selected"},
            "status_counts": dict(Counter(row["status"] for row in rows)),
            "strata": strata, "rows": rows,
            "scope": "Retrospective owner and routing calibration; no beneficial-control or live-fill proof."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    prepare_cmd = sub.add_parser("prepare")
    prepare_cmd.add_argument("session", type=Path)
    prepare_cmd.add_argument("--out", type=Path, required=True)
    fetch_cmd = sub.add_parser("fetch")
    fetch_cmd.add_argument("selection", type=Path)
    fetch_cmd.add_argument("--responses", type=Path, required=True)
    fetch_cmd.add_argument("--rpc-url", default=RPC)
    fetch_cmd.add_argument("--pace-seconds", type=float, default=1.2)
    report_cmd = sub.add_parser("report")
    report_cmd.add_argument("session", type=Path)
    report_cmd.add_argument("selection", type=Path)
    report_cmd.add_argument("--responses", type=Path, required=True)
    report_cmd.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        result = select(args.session)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({key: value for key, value in result.items() if key != "selected"}, indent=2))
    elif args.action == "fetch":
        if not 0 <= args.pace_seconds <= 10:
            parser.error("pace-seconds must be 0..10")
        fetch(args.selection, args.responses, args.pace_seconds, args.rpc_url)
    else:
        result = report(args.session, args.selection, args.responses)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"status_counts": result["status_counts"],
                          "strata": result["strata"]}, indent=2))
