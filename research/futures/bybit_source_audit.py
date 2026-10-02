"""Audit public Bybit instrument metadata against observed price/funding coverage.

This probes data availability only. It does not calculate returns or select a
trading universe from today's metadata. Raw API responses remain in an ignored
local directory with hashes so observed coverage can be reproduced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

BASE = "https://api.bybit.com/v5/market"
DAY_MS = 86_400_000


def request_json(path: str, params: dict, *, timeout: float = 20.0) -> tuple[bytes, dict]:
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "rocket-research-coverage/1"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
            payload = json.loads(raw)
            if payload.get("retCode") == 0 and isinstance(payload.get("result"), dict):
                return raw, payload
            if payload.get("retCode") not in (10006, 10016):
                raise ValueError(f"Bybit API error: {path} {payload.get('retCode')} ")
        except (OSError, TimeoutError):
            if attempt == 3:
                raise
        if attempt == 3:
            raise ValueError(f"Bybit API retry exhaustion: {path}")
        time.sleep(1 + attempt)
    raise AssertionError("unreachable")


def save_response(output: Path, name: str, raw: bytes) -> str:
    output.mkdir(parents=True, exist_ok=True)
    (output / name).write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def matching_usdt_perpetuals(items: list[dict], status: str) -> list[dict]:
    return [item for item in items
            if item.get("contractType") == "LinearPerpetual"
            and item.get("quoteCoin") == "USDT"
            and item.get("status") == status]


def catalog(output: Path) -> tuple[list[dict], list[dict]]:
    pages = []
    contracts = []
    for status in ("Trading", "Closed"):
        cursor = ""
        seen = set()
        page = 0
        while True:
            params = {"category": "linear", "status": status, "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            raw, payload = request_json("/instruments-info", params)
            digest = save_response(output, f"instruments_{status}_{page}.json", raw)
            result = payload["result"]
            items = result.get("list", [])
            pages.append({"requested_status": status, "page": page, "records": len(items),
                          "returned_statuses": dict(Counter(item.get("status") for item in items)),
                          "sha256": digest})
            contracts.extend(matching_usdt_perpetuals(items, status))
            cursor = result.get("nextPageCursor") or ""
            if not cursor:
                break
            if cursor in seen:
                raise ValueError("repeated Bybit catalog cursor")
            seen.add(cursor)
            page += 1
    symbols = [item["symbol"] for item in contracts]
    if len(symbols) != len(set(symbols)):
        raise ValueError("duplicate active/closed Bybit symbol")
    return contracts, pages


def pick_sample(contracts: list[dict], *, each: int = 12) -> list[dict]:
    """Fixed old/survivor/closed mix; this is a source audit, not a backtest."""
    cutoff = int(datetime(2023, 1, 1, tzinfo=UTC).timestamp() * 1000)
    groups = {}
    for status in ("Trading", "Closed"):
        groups[status] = sorted((item for item in contracts
                                 if item.get("status") == status
                                 and 0 < int(item.get("launchTime") or 0) < cutoff),
                                key=lambda item: (int(item["launchTime"]), item["symbol"]))
    sample = groups["Trading"][:each] + groups["Closed"][:each]
    if len(sample) < 2 * each:
        raise ValueError("too few old active/closed USDT perpetuals")
    return sample


def window_bounds(item: dict, kind: str) -> tuple[int, int]:
    launch = int(item["launchTime"])
    delivery = int(item.get("deliveryTime") or 0)
    if kind == "first":
        first = (launch // DAY_MS) * DAY_MS
        return first, first + 30 * DAY_MS
    if kind == "last" and delivery:
        end = ((delivery + DAY_MS - 1) // DAY_MS) * DAY_MS
        return end - 30 * DAY_MS, end
    raise ValueError(f"invalid coverage window: {item['symbol']} {kind}")


def probe(item: dict, kind: str, output: Path) -> dict:
    start, end = window_bounds(item, kind)
    symbol = item["symbol"]
    measures = {}
    for source, path, params, list_key, stamp_index in (
        ("daily", "/kline", {"category": "linear", "symbol": symbol,
                               "interval": "D", "start": start, "end": end - DAY_MS,
                               "limit": 1000}, "list", 0),
        ("funding", "/funding/history", {"category": "linear", "symbol": symbol,
                                         "startTime": start, "endTime": end - 1,
                                         "limit": 1000}, "list", None),
    ):
        raw, payload = request_json(path, params)
        digest = save_response(output, f"{symbol}_{kind}_{source}.json", raw)
        rows = payload["result"].get(list_key, [])
        stamps = [int(row[stamp_index] if stamp_index is not None
                      else row["fundingRateTimestamp"]) for row in rows]
        if len(stamps) != len(set(stamps)) or any(not start <= stamp < end for stamp in stamps):
            raise ValueError(f"invalid timestamps in {symbol} {kind} {source}")
        measures[source] = {"rows": len(rows), "first_ms": min(stamps) if stamps else None,
                            "last_ms": max(stamps) if stamps else None, "sha256": digest}
        if source == "daily":
            expected = set(range(start, end, DAY_MS))
            measures[source]["missing_days"] = len(expected - set(stamps))
        else:
            ordered = sorted(stamps)
            measures[source]["max_gap_hours"] = (max((right - left) / 3_600_000
                                                    for left, right in pairwise(ordered))
                                                    if len(ordered) > 1 else None)
    return {"symbol": symbol, "status": item["status"], "kind": kind,
            "launch_ms": int(item["launchTime"]),
            "delivery_ms": int(item.get("deliveryTime") or 0),
            "window_start_ms": start, "window_end_ms": end,
            **measures}


def run(output: Path) -> dict:
    contracts, pages = catalog(output)
    sample = pick_sample(contracts)
    results = []
    for item in sample:
        results.append(probe(item, "first", output))
        if item["status"] == "Closed":
            results.append(probe(item, "last", output))
    summary = Counter((item["status"], item["kind"]) for item in results)
    report = {"meaning": "read-only Bybit source availability audit; no strategy outcomes",
              "retrieved_at": datetime.now(UTC).isoformat(),
              "catalog_pages": pages,
              "usdt_perpetuals_by_status": dict(Counter(item["status"] for item in contracts)),
              "sample_rule": "earliest 12 pre-2023 Trading and earliest 12 pre-2023 Closed",
              "sample_windows": {f"{status}_{kind}": count
                                 for (status, kind), count in summary.items()},
              "results": results}
    (output / "source_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = run(args.output)
    print(json.dumps({"contracts": report["usdt_perpetuals_by_status"],
                      "windows": report["sample_windows"],
                      "report": str(args.output / "source_audit.json")}, indent=2))


if __name__ == "__main__":
    main()
