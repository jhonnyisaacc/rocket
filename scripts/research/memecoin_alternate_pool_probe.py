"""MC-012 later pool-discovery diagnostic, with explicit original exit clocks."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

URL = "https://api.dexscreener.com/tokens/v1/solana/"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def select(session: Path) -> dict:
    source = session / "universe.jsonl"
    universe = [json.loads(line) for line in source.read_text().splitlines()]
    unavailable = [row for row in universe if row.get("reason") ==
                   "EXIT_UNAVAILABLE:insufficient exit liquidity"]
    quoted = [row for row in universe if row["status"] == "QUOTED"]
    quoted.sort(key=lambda row: (digest(f"mc012:{row['mint']}".encode()), row["mint"]))
    if not unavailable or len(quoted) < len(unavailable):
        raise ValueError("MC-012 source population differs from frozen groups")
    selected = []
    for group, rows in (("curve_unavailable", unavailable),
                        ("quoted_control", quoted[:len(unavailable)])):
        for row in rows:
            created = datetime.fromisoformat(row["created_available_at"])
            selected.append({"mint": row["mint"], "group": group,
                             "create_received_at": created.isoformat(),
                             "frozen_exit_at": (created + timedelta(seconds=67)).isoformat()})
    return {"schema": "rocket.memecoin.mc012-pool-selection.v1",
            "universe_sha256": digest(source.read_bytes()),
            "method": "all curve-unavailable; equal quoted controls by sha256('mc012:' + mint)",
            "unavailable_population": len(unavailable), "quoted_population": len(quoted),
            "selected": selected}


def batches(selection: dict) -> list[list[str]]:
    mints = [row["mint"] for row in selection["selected"]]
    return [mints[index:index + 30] for index in range(0, len(mints), 30)]


def fetch(selection_path: Path, out: Path, pace: float) -> None:
    selection = json.loads(selection_path.read_text())
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=20) as client:
        for number, mints in enumerate(batches(selection)):
            path = out / f"batch-{number:03d}.json"
            attempts = json.loads(path.read_text())["attempts"] if path.exists() else []
            if any(item.get("http_status") == 200 and isinstance(item.get("body"), list)
                   for item in attempts):
                continue
            for attempt in range(1, 4):
                requested_at = datetime.now(UTC).isoformat()
                try:
                    response = client.get(URL + ",".join(mints))
                    item = {"requested_at": requested_at,
                            "received_at": datetime.now(UTC).isoformat(),
                            "http_status": response.status_code,
                            "raw_response_sha256": digest(response.content),
                            "body": response.json()}
                except (httpx.HTTPError, ValueError) as exc:
                    item = {"requested_at": requested_at,
                            "received_at": datetime.now(UTC).isoformat(),
                            "error": type(exc).__name__}
                attempts.append(item)
                path.write_text(json.dumps({"schema": "rocket.memecoin.mc012-pool-batch.v1",
                                            "batch_number": number, "requested_mints": mints,
                                            "endpoint_host": "api.dexscreener.com",
                                            "attempts": attempts}, sort_keys=True) + "\n")
                if item.get("http_status") == 200 and isinstance(item.get("body"), list):
                    break
                time.sleep(pace * attempt)
            time.sleep(pace)


def report(session: Path, selection_path: Path, response_dir: Path) -> dict:
    selection = json.loads(selection_path.read_text())
    if selection != select(session):
        raise ValueError("selection differs from frozen MC-010 source")
    pair_rows: dict[str, list[dict]] = {row["mint"]: [] for row in selection["selected"]}
    status: dict[str, str] = {mint: "NOT_FETCHED" for mint in pair_rows}
    response_hashes = []
    for number, mints in enumerate(batches(selection)):
        path = response_dir / f"batch-{number:03d}.json"
        if not path.exists():
            continue
        record = json.loads(path.read_text())
        if record["requested_mints"] != mints:
            raise ValueError("batch request differs from frozen selection")
        response_hashes.append({"batch": number, "sha256": digest(path.read_bytes()),
                                "attempt_count": len(record["attempts"])})
        successful = next((item for item in reversed(record["attempts"])
                           if item.get("http_status") == 200 and isinstance(
                               item.get("body"), list)), None)
        if successful is None:
            for mint in mints:
                status[mint] = "FETCH_FAILED"
            continue
        for mint in mints:
            status[mint] = "LISTED_RESPONSE"
        for pair in successful["body"]:
            if not isinstance(pair, dict) or pair.get("chainId") != "solana":
                continue
            addresses = {(pair.get("baseToken") or {}).get("address"),
                         (pair.get("quoteToken") or {}).get("address")}
            for mint in addresses & pair_rows.keys():
                if mint in mints:
                    pair_rows[mint].append(pair)
    rows = []
    for selected in selection["selected"]:
        mint = selected["mint"]
        exit_at = datetime.fromisoformat(selected["frozen_exit_at"])
        unique = {pair.get("pairAddress"): pair for pair in pair_rows[mint]
                  if isinstance(pair.get("pairAddress"), str)}
        pairs = []
        for address, pair in sorted(unique.items()):
            created_ms = pair.get("pairCreatedAt")
            created_at = (datetime.fromtimestamp(created_ms / 1000, UTC).isoformat()
                          if isinstance(created_ms, int) else None)
            pairs.append({"pair_address": address, "dex_id": pair.get("dexId"),
                          "base_mint": (pair.get("baseToken") or {}).get("address"),
                          "quote_mint": (pair.get("quoteToken") or {}).get("address"),
                          "pair_created_at": created_at,
                          "creation_time_screen": ("AT_OR_BEFORE_EXIT" if created_at
                                                   and datetime.fromisoformat(created_at) <= exit_at
                                                   else "AFTER_EXIT" if created_at else "UNKNOWN")})
        other = [pair for pair in pairs if pair["dex_id"] != "pumpfun"]
        row_status = status[mint] if pairs else (
            "NO_LISTED_PAIRS_AT_LATER_CHECK" if status[mint] == "LISTED_RESPONSE" else status[mint])
        rows.append({**selected, "status": row_status, "pairs": pairs,
                     "other_venue_pair_count": len(other),
                     "other_venue_at_or_before_exit_timestamp_count": sum(
                         pair["creation_time_screen"] == "AT_OR_BEFORE_EXIT" for pair in other)})
    groups = {}
    for group in ("curve_unavailable", "quoted_control"):
        subset = [row for row in rows if row["group"] == group]
        groups[group] = {"selected": len(subset),
                         "status_counts": dict(Counter(row["status"] for row in subset)),
                         "any_other_venue_later": sum(row["other_venue_pair_count"] > 0
                                                      for row in subset),
                         "other_venue_timestamp_candidate": sum(
                             row["other_venue_at_or_before_exit_timestamp_count"] > 0
                             for row in subset)}
    return {"schema": "rocket.memecoin.mc012-pool-probe.v1",
            "selection_sha256": digest(selection_path.read_bytes()),
            "response_hashes": response_hashes, "groups": groups, "rows": rows,
            "scope": "Later third-party discovery only; no as-of liquidity or executable quote."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    prepare_cmd = sub.add_parser("prepare")
    prepare_cmd.add_argument("session", type=Path)
    prepare_cmd.add_argument("--out", type=Path, required=True)
    fetch_cmd = sub.add_parser("fetch")
    fetch_cmd.add_argument("selection", type=Path)
    fetch_cmd.add_argument("--responses", type=Path, required=True)
    fetch_cmd.add_argument("--pace-seconds", type=float, default=1.0)
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
        fetch(args.selection, args.responses, args.pace_seconds)
    else:
        result = report(args.session, args.selection, args.responses)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result["groups"], indent=2))
