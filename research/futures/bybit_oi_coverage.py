"""Audit 2022 Bybit daily OI against the existing observed-bar candidate universe.

Fetches no strategy outcomes. Raw public API responses remain outside Git,
while the report records their hashes and all source-coverage exceptions.
"""

from __future__ import annotations

import argparse
import collections
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
import time

from research.futures.bybit_source_audit import DAY_MS, request_json


START = int(datetime(2022, 1, 1, tzinfo=UTC).timestamp() * 1000)
END = int(datetime(2023, 1, 1, tzinfo=UTC).timestamp() * 1000)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def get_page(output: Path, symbol: str, end_exclusive: int, page: int) -> tuple[list[dict], dict]:
    name = f"{symbol}_2022_{page:03d}_{end_exclusive}.json"
    path = output / "raw" / name
    if path.exists():
        raw = path.read_bytes()
        payload = json.loads(raw)
    else:
        raw, payload = request_json("/open-interest", {
            "category": "linear", "symbol": symbol, "intervalTime": "1d",
            "startTime": START, "endTime": end_exclusive - 1, "limit": 200,
        })
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        time.sleep(0.06)
    result = payload.get("result", {})
    if payload.get("retCode") != 0 or result.get("symbol") != symbol:
        raise ValueError(f"invalid OI source page {name}")
    rows = result.get("list", [])
    stamps = [int(row["timestamp"]) for row in rows]
    if len(stamps) != len(set(stamps)) or any(
        stamp % DAY_MS or not START <= stamp < end_exclusive for stamp in stamps
    ):
        raise ValueError(f"duplicate, unaligned or out-of-range OI timestamp: {name}")
    if any(float(row["openInterest"]) < 0 for row in rows):
        raise ValueError(f"negative OI: {name}")
    for row in rows:
        if "singleOpenInterest" in row:
            single = float(row["singleOpenInterest"])
            double = float(row["openInterest"])
            # The newer single-side field is rounded to a coarser contract
            # increment for some symbols; audit agreement to one basis point.
            if abs(2 * single - double) > max(1e-6, double * 1e-4):
                raise ValueError(f"single/double OI field mismatch: {name}")
    record = {"key": f"raw/{name}", "sha256": sha256(raw), "rows": len(rows),
              "end_exclusive_ms": end_exclusive}
    return rows, record


def collect(output: Path, symbol: str) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    records: list[dict] = []
    end = END
    for page in range(10):
        batch, record = get_page(output, symbol, end, page)
        records.append(record)
        rows.extend(batch)
        if len(batch) < 200:
            break
        next_end = min(int(row["timestamp"]) for row in batch)
        if next_end >= end or next_end <= START:
            break
        end = next_end
    else:
        raise ValueError(f"pagination exceeded 10 pages: {symbol}")
    stamps = [int(row["timestamp"]) for row in rows]
    if len(stamps) != len(set(stamps)):
        raise ValueError(f"overlap across OI pages: {symbol}")
    return rows, records


def audit(coverage_path: Path, output: Path) -> dict:
    raw_coverage = coverage_path.read_bytes()
    coverage = json.loads(raw_coverage)
    candidates = coverage["results"]
    if len(candidates) != 190 or coverage.get("failures"):
        raise ValueError("2022 candidate coverage is not the audited 190-symbol inventory")
    results = []
    failures = []
    source_rows = 0
    for index, candidate in enumerate(candidates, 1):
        symbol = candidate["symbol"]
        try:
            rows, records = collect(output, symbol)
            by_day = {int(row["timestamp"]): float(row["openInterest"]) for row in rows}
            first = candidate["first_price_ms"]
            last = candidate["last_price_ms"]
            active = set(range(max(START, first), min(END - DAY_MS, last) + 1, DAY_MS))
            observed = set(by_day)
            missing_active = sorted(active - observed)
            zero_active = sorted(day for day in active & observed if by_day[day] == 0)
            positive_outside = sorted(day for day in observed - active if by_day[day] > 0)
            source_rows += len(rows)
            results.append({
                "symbol": symbol, "status": candidate["status"],
                "active_price_days_2022": len(active), "oi_rows_2022": len(rows),
                "positive_oi_rows_2022": sum(value > 0 for value in by_day.values()),
                "missing_active_oi_days": len(missing_active),
                "zero_active_oi_days": len(zero_active),
                "positive_oi_outside_price_days": len(positive_outside),
                "first_missing_active_ms": missing_active[:5],
                "first_zero_active_ms": zero_active[:5],
                "first_positive_outside_ms": positive_outside[:5],
                "sources": records,
            })
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})
        if index % 20 == 0 or index == len(candidates):
            print(f"{index}/{len(candidates)} symbols; failures={len(failures)}", file=sys.stderr,
                  flush=True)
    counts = collections.Counter()
    for row in results:
        counts["active_price_days_2022"] += row["active_price_days_2022"]
        counts["oi_rows_2022"] += row["oi_rows_2022"]
        counts["missing_active_oi_days"] += row["missing_active_oi_days"]
        counts["zero_active_oi_days"] += row["zero_active_oi_days"]
        counts["positive_oi_outside_price_days"] += row["positive_oi_outside_price_days"]
        counts["symbols_with_complete_positive_active_oi"] += int(
            row["active_price_days_2022"] > 0
            and row["missing_active_oi_days"] == row["zero_active_oi_days"] == 0
        )
    return {
        "meaning": "return-free 2022 daily OI coverage versus observed Bybit price days",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "candidate_coverage_sha256": sha256(raw_coverage),
        "candidate_count": len(candidates), "total_source_rows": source_rows,
        "counts": dict(counts), "failures": failures, "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = audit(args.coverage, args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps({key: report[key] for key in ("candidate_count", "counts", "failures")},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
