"""Deterministic read-only MC-004 transaction-accounting calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

NATIVE_QUOTE = "11111111111111111111111111111111"
PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
TARGETS = {"single_buy": 24, "single_sell": 24, "multi_trade": 8}


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def select(session: Path) -> dict:
    source = session / "observations.jsonl"
    source_sha256 = digest(source.read_bytes())
    by_signature: dict[str, list[dict]] = defaultdict(list)
    for line in source.read_text().splitlines():
        row = json.loads(line)
        if row["event_type"] == "TradeEvent":
            by_signature[row["signature"]].append(row)
    strata: dict[str, list[str]] = defaultdict(list)
    for signature, events in by_signature.items():
        supported = [row for row in events if row["quote_mint"] == NATIVE_QUOTE
                     and not row["mayhem_mode"] and row["sol_amount"] > 0]
        if not supported:
            continue
        if len(events) == 1:
            name = "single_buy" if supported[0]["is_buy"] else "single_sell"
        else:
            name = "multi_trade"
        strata[name].append(signature)
    selected = []
    for name, target in TARGETS.items():
        signatures = sorted(strata[name], key=lambda sig: (digest(f"mc004:{sig}".encode()), sig))
        for signature in signatures[:target]:
            events = by_signature[signature]
            selected.append({"signature": signature, "stratum": name,
                             "slot": events[0]["slot"], "mint": events[0]["mint"],
                             "event_count": len(events),
                             "supported_event_count": sum(
                                 row["quote_mint"] == NATIVE_QUOTE and not row["mayhem_mode"]
                                 and row["sol_amount"] > 0 for row in events),
                             "event_token_amount": events[0]["token_amount"] if len(events) == 1 else None})
    return {"schema": "rocket.memecoin.mc004-selection.v1",
            "source_sha256": source_sha256,
            "method": "sha256('mc004:' + signature) ascending, per stratum",
            "population": {name: len(strata[name]) for name in TARGETS},
            "target": TARGETS, "selected": selected}


def fetch(session: Path, out: Path, *, rpc_url: str, pace: float) -> None:
    selection = select(session)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "selection.json"
    if path.exists():
        if json.loads(path.read_text()) != selection:
            raise ValueError("saved sample selection differs from source")
    else:
        path.write_text(json.dumps(selection, indent=2) + "\n")
    responses = out / "responses"
    responses.mkdir(exist_ok=True)
    with httpx.Client(timeout=20) as client:
        for row in selection["selected"]:
            signature = row["signature"]
            result_path = responses / f"{signature}.json"
            attempts = []
            if result_path.exists():
                attempts = json.loads(result_path.read_text())["attempts"]
                if any(item.get("body", {}).get("result") for item in attempts):
                    continue
            for attempt in range(3):
                requested_at = datetime.now(UTC).isoformat()
                try:
                    response = client.post(rpc_url, json={
                        "jsonrpc": "2.0", "id": 1, "method": "getTransaction",
                        "params": [signature, {"encoding": "jsonParsed", "commitment": "confirmed",
                                               "maxSupportedTransactionVersion": 1}],
                    })
                    body = response.json()
                    received_at = datetime.now(UTC).isoformat()
                    attempts.append({"requested_at": requested_at, "received_at": received_at,
                                     "max_supported_transaction_version": 1,
                                     "http_status": response.status_code, "body": body})
                    if response.is_success and body.get("result"):
                        break
                except (httpx.HTTPError, ValueError) as exc:
                    attempts.append({"requested_at": requested_at,
                                     "received_at": datetime.now(UTC).isoformat(),
                                     "max_supported_transaction_version": 1,
                                     "error": type(exc).__name__})
                time.sleep(pace)
            record = {"signature": signature, "rpc_host": urlparse(rpc_url).hostname,
                      "attempts": attempts}
            result_path.write_text(json.dumps(record, sort_keys=True) + "\n")
            time.sleep(pace)


def token_amounts(meta: dict, mint: str) -> dict[int, int]:
    before = {row["accountIndex"]: int(row["uiTokenAmount"]["amount"])
              for row in meta.get("preTokenBalances") or [] if row["mint"] == mint}
    after = {row["accountIndex"]: int(row["uiTokenAmount"]["amount"])
             for row in meta.get("postTokenBalances") or [] if row["mint"] == mint}
    return {index: after.get(index, 0) - before.get(index, 0)
            for index in before.keys() | after.keys()}


def report(session: Path, out: Path) -> dict:
    selection = select(session)
    if json.loads((out / "selection.json").read_text()) != selection:
        raise ValueError("saved sample selection differs from source")
    create_signatures = {row["signature"] for line in (session / "observations.jsonl").read_text().splitlines()
                         if (row := json.loads(line))["event_type"] == "CreateEvent"}
    rows = []
    for chosen in selection["selected"]:
        path = out / "responses" / f"{chosen['signature']}.json"
        if not path.exists():
            rows.append({**chosen, "status": "NOT_FETCHED"})
            continue
        raw = path.read_bytes()
        record = json.loads(raw)
        attempts = record["attempts"]
        body = next((item["body"] for item in reversed(attempts)
                     if item.get("body", {}).get("result")), None)
        tx = body.get("result") if body else None
        result = {**chosen, "response_sha256": digest(raw),
                  "rpc_host": record["rpc_host"], "attempt_count": len(attempts)}
        if tx is None:
            rows.append({**result, "status": "UNAVAILABLE"})
            continue
        if chosen["signature"] not in tx["transaction"]["signatures"] or tx["slot"] != chosen["slot"]:
            rows.append({**result, "status": "IDENTITY_MISMATCH"})
            continue
        meta = tx["meta"]
        if meta is None or meta["err"] is not None:
            rows.append({**result, "status": "FAILED_TRANSACTION"})
            continue
        keys = tx["transaction"]["message"]["accountKeys"]
        instructions = tx["transaction"]["message"]["instructions"]
        direct = any(item.get("programId") == PUMP_PROGRAM for item in instructions)
        token_deltas = token_amounts(meta, chosen["mint"])
        nonzero_token_deltas = sorted(value for value in token_deltas.values() if value)
        amount = chosen["event_token_amount"]
        if amount is None:
            token_check = "MULTI_EVENT_AMBIGUOUS"
        elif nonzero_token_deltas == [-amount, amount]:
            token_check = "MATCHED_TWO_ACCOUNTS"
        elif chosen["signature"] in create_signatures and amount in nonzero_token_deltas:
            token_check = "CREATE_WITHOUT_PRE_BALANCE"
        else:
            token_check = "AMBIGUOUS_OR_MISMATCH"
        rows.append({**result, "status": "VERIFIED_TRANSACTION", "fee_lamports": meta["fee"],
                     "fee_payer": keys[0]["pubkey"], "top_level_pump": direct,
                     "top_level_instruction_count": len(instructions),
                     "token_deltas": token_deltas, "token_check": token_check,
                     "observed_create_same_tx": chosen["signature"] in create_signatures,
                     "fee_payer_balance_delta": meta["postBalances"][0] - meta["preBalances"][0],
                     "balance_deltas": [post - pre for pre, post in zip(
                         meta["preBalances"], meta["postBalances"], strict=True)]})
    summary = {"schema": "rocket.memecoin.mc004-accounting.v1",
               "selection_sha256": digest((out / "selection.json").read_bytes()),
               "rows": rows, "status_counts": dict(Counter(row["status"] for row in rows)),
               "strata": {name: {"population": selection["population"][name],
                                  "selected": sum(row["stratum"] == name for row in rows),
                                  "verified": sum(row["stratum"] == name and row["status"] ==
                                                  "VERIFIED_TRANSACTION" for row in rows),
                                  "fee_lamports_median": statistics.median(
                                      fees) if (fees := [row["fee_lamports"] for row in rows
                                                     if row["stratum"] == name and
                                                     row["status"] == "VERIFIED_TRANSACTION"]) else None,
                                  "fee_lamports_min": min(fees) if fees else None,
                                  "fee_lamports_max": max(fees) if fees else None}
                          for name in TARGETS}}
    (out / "report.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--rpc-url", default="https://solana-rpc.publicnode.com")
    parser.add_argument("--pace-seconds", type=float, default=1.2)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.pace_seconds <= 10:
        parser.error("pace must be 0..10 seconds")
    if not args.report_only:
        fetch(args.session, args.out, rpc_url=args.rpc_url, pace=args.pace_seconds)
    print(json.dumps(report(args.session, args.out), indent=2))
