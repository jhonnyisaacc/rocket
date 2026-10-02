"""Probe historical minute index/trade coverage around Bybit 2022 closures.

These minute windows are unscored data candidates, not accepted settlement
prices. Official venue rules and exact closing prices remain separate checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from research.futures.bybit_source_audit import request_json

MINUTE_MS = 60_000
SYMBOLS = ("LUNAUSDT", "FTTUSDT", "SRMUSDT")


def mean_envelope(rows: dict[int, list], cutoff: int, minutes: int) -> dict | None:
    window = [rows.get(cutoff - step * MINUTE_MS) for step in range(1, minutes + 1)]
    if any(row is None for row in window):
        return None
    return {"mean_low": sum(float(row[3]) for row in window) / minutes,
            "mean_close": sum(float(row[4]) for row in window) / minutes,
            "mean_high": sum(float(row[2]) for row in window) / minutes}


def probe(symbol: str, cutoff: int, output: Path) -> dict:
    start = cutoff - 60 * MINUTE_MS
    end = cutoff + 5 * MINUTE_MS
    sources = {}
    parsed = {}
    for kind, endpoint in (("index", "/index-price-kline"),
                           ("trade", "/kline")):
        raw, payload = request_json(endpoint, {"category": "linear", "symbol": symbol,
                                               "interval": "1", "start": start,
                                               "end": end, "limit": 200})
        key = f"{symbol}_{kind}_{start}_{end}.json"
        (output / key).write_bytes(raw)
        rows = payload["result"].get("list", [])
        by_time = {int(row[0]): row for row in rows}
        if len(rows) != len(by_time) or any(stamp < start or stamp > end
                                            for stamp in by_time):
            raise ValueError(f"invalid Bybit minute index: {symbol} {kind}")
        sources[kind] = {"key": key, "sha256": hashlib.sha256(raw).hexdigest(),
                         "rows": len(rows)}
        parsed[kind] = by_time
    active = sorted(stamp for stamp, row in parsed["trade"].items()
                    if float(row[5]) > 0)
    index = parsed["index"]
    return {"symbol": symbol, "reported_delivery_ms": cutoff,
            "last_active_trade_minute_ms": active[-1] if active else None,
            "last_index_minute_ms": max(index) if index else None,
            "index_30m": mean_envelope(index, cutoff, 30),
            "index_60m": mean_envelope(index, cutoff, 60),
            "index_at_cutoff": index.get(cutoff),
            "sources": sources}


def run(coverage: Path, output: Path) -> dict:
    manifest = json.loads(coverage.read_text())
    by_symbol = {item["symbol"]: item for item in manifest["results"]}
    output.mkdir(parents=True, exist_ok=True)
    events = [probe(symbol, by_symbol[symbol]["reported_delivery_ms"], output)
              for symbol in SYMBOLS]
    report = {"meaning": "unscored Bybit closure minute-data candidates",
              "retrieved_at": datetime.now(UTC).isoformat(), "events": events}
    (output / "settlement_probe.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = run(args.coverage, args.output)
    print(json.dumps({"events": len(report["events"]),
                      "complete_30m": sum(item["index_30m"] is not None
                                          for item in report["events"]),
                      "complete_60m": sum(item["index_60m"] is not None
                                          for item in report["events"]),
                      "report": str(args.output / "settlement_probe.json")}, indent=2))


if __name__ == "__main__":
    main()
