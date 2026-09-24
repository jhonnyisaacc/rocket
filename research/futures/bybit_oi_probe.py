"""Probe historical Bybit open-interest API availability without signal returns.

Five fixed symbol/month windows test old, recent and closed contracts. Raw API
responses and their hashes stay in an ignored local research directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from research.futures.bybit_source_audit import request_json

WINDOWS = (("BTCUSDT", "2022-01"), ("ETHUSDT", "2022-01"),
           ("FTTUSDT", "2022-11"), ("BTCUSDT", "2024-01"),
           ("BTCUSDT", "2025-01"))


def month_bounds(month: str) -> tuple[int, int]:
    start = datetime.fromisoformat(month + "-01").replace(tzinfo=UTC)
    year, month_number = divmod(start.month, 12)
    end = datetime(start.year + year, month_number + 1, 1, tzinfo=UTC)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def probe(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for symbol, month in WINDOWS:
        start, end = month_bounds(month)
        name = f"{symbol}_{month}_1d.json"
        path = output / name
        if path.exists():
            raw = path.read_bytes()
            payload = json.loads(raw)
        else:
            raw, payload = request_json("/open-interest", {
                "category": "linear", "symbol": symbol, "intervalTime": "1d",
                "startTime": start, "endTime": end - 1, "limit": 200})
            path.write_bytes(raw)
        if payload.get("retCode") != 0 or payload.get("result", {}).get("symbol") != symbol:
            raise ValueError(f"invalid Bybit OI response: {name}")
        rows = payload["result"].get("list", [])
        stamps = [int(row["timestamp"]) for row in rows]
        if len(stamps) != len(set(stamps)) or any(not start <= stamp < end for stamp in stamps):
            raise ValueError(f"duplicate or out-of-window OI timestamp: {name}")
        if any(float(row["openInterest"]) < 0 for row in rows):
            raise ValueError(f"negative OI: {name}")
        results.append({"symbol": symbol, "month": month, "rows": len(rows),
                        "first_day": datetime.fromtimestamp(min(stamps) / 1000, UTC).date().isoformat()
                        if stamps else None,
                        "last_day": datetime.fromtimestamp(max(stamps) / 1000, UTC).date().isoformat()
                        if stamps else None,
                        "source_key": name, "sha256": hashlib.sha256(raw).hexdigest(),
                        "next_page_cursor_present": bool(payload["result"].get("nextPageCursor")),
                        "server_time_ms": payload.get("time")})
    return {"retrieved_at": datetime.now(UTC).isoformat(),
            "meaning": "five fixed OI source windows only; no universe or forecast claim",
            "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(probe(args.output), indent=2))


if __name__ == "__main__":
    main()
