"""Resumable source-availability inventory for 2020-2022 Bybit USDT perps.

Collects daily candle and funding timestamps only for coverage decisions. Raw
API responses are retained with hashes. It never calculates strategy returns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

from research.futures.bybit_source_audit import (
    DAY_MS,
    matching_usdt_perpetuals,
    request_json,
)

START_MS = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
END_MS = int(datetime(2023, 1, 1, tzinfo=UTC).timestamp() * 1000)
PRICE_WINDOWS = (("2020-2021", START_MS, int(datetime(2022, 1, 1, tzinfo=UTC).timestamp() * 1000)),
                 ("2022", int(datetime(2022, 1, 1, tzinfo=UTC).timestamp() * 1000), END_MS))
FUNDING_WINDOWS = tuple(
    (f"{year}-{half}",
     int(datetime(year, 1 if half == 1 else 7, 1, tzinfo=UTC).timestamp() * 1000),
     int(datetime(year + 1 if half == 2 else year,
                  1 if half == 2 else 7, 1, tzinfo=UTC).timestamp() * 1000))
    for year in (2020, 2021, 2022) for half in (1, 2))


def candidates(catalog: Path) -> list[dict]:
    symbols = {}
    for status in ("Trading", "Closed"):
        page = 0
        while True:
            path = catalog / f"instruments_{status}_{page}.json"
            payload = json.loads(path.read_bytes())
            if payload.get("retCode") != 0:
                raise ValueError(f"invalid catalog page: {path}")
            for item in matching_usdt_perpetuals(payload["result"]["list"], status):
                if 0 < int(item.get("launchTime") or 0) < END_MS:
                    if item["symbol"] in symbols:
                        raise ValueError(f"duplicate catalog symbol: {item['symbol']}")
                    symbols[item["symbol"]] = item
            if not payload["result"].get("nextPageCursor"):
                break
            page += 1
    return [symbols[symbol] for symbol in sorted(symbols)]


def source_response(output: Path, symbol: str, kind: str, start: int,
                    end: int) -> tuple[list, dict]:
    name = f"{symbol}_{kind}_{start}_{end}{'_limit200' if kind == 'funding' else ''}.json"
    path = output / "raw" / name
    if path.exists():
        raw = path.read_bytes()
        payload = json.loads(raw)
    else:
        if kind == "daily":
            endpoint = "/kline"
            params = {"category": "linear", "symbol": symbol, "interval": "D",
                      "start": start, "end": end - DAY_MS, "limit": 1000}
        else:
            endpoint = "/funding/history"
            params = {"category": "linear", "symbol": symbol,
                      "startTime": start, "endTime": end - 1, "limit": 200}
        raw, payload = request_json(endpoint, params)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    if payload.get("retCode") != 0:
        raise ValueError(f"bad Bybit response: {name}")
    rows = payload["result"].get("list", [])
    if kind == "daily":
        if payload["result"].get("symbol") != symbol:
            raise ValueError(f"bad Bybit response symbol: {name}")
    elif any(row.get("symbol") != symbol for row in rows):
        raise ValueError(f"bad Bybit funding symbol: {name}")
    stamps = [int(row[0] if kind == "daily" else row["fundingRateTimestamp"])
              for row in rows]
    if len(stamps) != len(set(stamps)) or any(not start <= stamp < end for stamp in stamps):
        raise ValueError(f"duplicate or out-of-range Bybit timestamp: {name}")
    if kind == "daily" and any(stamp % DAY_MS for stamp in stamps):
        raise ValueError(f"unaligned daily bar: {name}")
    record = {"key": str(path.relative_to(output)), "sha256": hashlib.sha256(raw).hexdigest(),
              "rows": len(rows), "start_ms": start, "end_ms": end}
    return stamps, record


def collect_window(output: Path, symbol: str, kind: str, start: int,
                   end: int) -> tuple[list[int], list[dict]]:
    if kind == "funding":
        stamps_all = []
        sources = []
        cursor = end
        while cursor > start:
            stamps, record = source_response(output, symbol, kind, start, cursor)
            stamps_all.extend(stamps)
            sources.append(record)
            if len(stamps) < 200 or min(stamps) <= start:
                break
            next_cursor = min(stamps)
            if next_cursor >= cursor:
                raise ValueError(f"stalled Bybit funding pagination: {symbol}")
            cursor = next_cursor
        if len(stamps_all) != len(set(stamps_all)):
            raise ValueError(f"duplicate Bybit funding pagination: {symbol}")
        return stamps_all, sources
    stamps, record = source_response(output, symbol, kind, start, end)
    if len(stamps) < 1000:
        return stamps, [record]
    days = (end - start) // DAY_MS
    if days < 2:
        raise ValueError(f"Bybit response cap inside one day: {symbol} {kind} {start}")
    middle = start + (days // 2) * DAY_MS
    left, left_sources = collect_window(output, symbol, kind, start, middle)
    right, right_sources = collect_window(output, symbol, kind, middle, end)
    if set(left) & set(right):
        raise ValueError(f"overlapping Bybit pagination: {symbol} {kind}")
    return left + right, left_sources + right_sources


def coverage(stamps: list[int], funding: list[int]) -> dict:
    days = sorted(set(stamps))
    slots = sorted(set(funding))
    internal_gaps = sum((right - left) // DAY_MS - 1 for left, right in pairwise(days))
    funding_days = {stamp // DAY_MS for stamp in slots}
    return {"price_days": len(days), "funding_rows": len(slots),
            "first_price_ms": days[0] if days else None,
            "last_price_ms": days[-1] if days else None,
            "first_funding_ms": slots[0] if slots else None,
            "last_funding_ms": slots[-1] if slots else None,
            "internal_price_gap_days": internal_gaps,
            "price_days_with_funding_stamp": sum(day // DAY_MS in funding_days for day in days),
            "max_funding_gap_hours": (max((right - left) / 3_600_000
                                      for left, right in pairwise(slots))
                                      if len(slots) > 1 else None)}


def audit_symbol(output: Path, item: dict) -> dict:
    symbol = item["symbol"]
    price = []
    funding = []
    sources = []
    for _, start, end in PRICE_WINDOWS:
        stamps, records = collect_window(output, symbol, "daily", start, end)
        price.extend(stamps)
        sources.extend(records)
    for _, start, end in FUNDING_WINDOWS:
        stamps, records = collect_window(output, symbol, "funding", start, end)
        funding.extend(stamps)
        sources.extend(records)
    if len(price) != len(set(price)) or len(funding) != len(set(funding)):
        raise ValueError(f"duplicate cross-window timestamp: {symbol}")
    return {"symbol": symbol, "status": item["status"],
            "reported_launch_ms": int(item["launchTime"]),
            "reported_delivery_ms": int(item.get("deliveryTime") or 0),
            **coverage(price, funding), "sources": sources}


def run(catalog: Path, output: Path, *, workers: int = 4) -> dict:
    items = candidates(catalog)
    results = []
    failures = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(audit_symbol, output, item): item["symbol"] for item in items}
        for index, future in enumerate(as_completed(jobs), 1):
            symbol = jobs[future]
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": str(exc)})
            if index % 20 == 0 or index == len(jobs):
                print(f"Bybit coverage: {index}/{len(jobs)}, failures={len(failures)}",
                      file=sys.stderr, flush=True)
    report = {"meaning": "2020-2022 source timestamp coverage; no strategy returns",
              "retrieved_at": datetime.now(UTC).isoformat(),
              "candidate_count": len(items),
              "candidate_statuses": dict(Counter(item["status"] for item in items)),
              "results": sorted(results, key=lambda item: item["symbol"]),
              "failures": sorted(failures, key=lambda item: item["symbol"])}
    output.mkdir(parents=True, exist_ok=True)
    (output / "coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    report = run(args.catalog, args.output, workers=args.workers)
    print(json.dumps({"candidates": report["candidate_count"],
                      "completed": len(report["results"]),
                      "failures": len(report["failures"]),
                      "report": str(args.output / "coverage.json")}, indent=2))


if __name__ == "__main__":
    main()
