"""Audit full 2024–2025 Hyperliquid BTC/ETH funding and daily candle coverage.

The API paginates time-range responses. Half-month funding requests stay below
the documented 500-element cap. Raw responses are cached before any analysis.
This tool does not compute funding spreads, returns, or strategy outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from research.futures.hyperliquid_carry_source_probe import DAY_MS, HOUR_MS, request_json

COINS = ("BTC", "ETH")
YEARS = (2024, 2025)


def milliseconds(year: int, month: int, day: int = 1) -> int:
    return int(datetime(year, month, day, tzinfo=UTC).timestamp() * 1000)


def periods() -> list[tuple[str, int, int, str]]:
    windows = []
    for year in YEARS:
        for month in range(1, 13):
            start = milliseconds(year, month)
            middle = milliseconds(year, month, 16)
            end = milliseconds(year + (month == 12), month % 12 + 1)
            windows.extend([("fundingHistory", start, middle, f"{year}-{month:02d}-01_15"),
                            ("fundingHistory", middle, end, f"{year}-{month:02d}-16_end")])
        windows.append(("candleSnapshot", milliseconds(year, 1), milliseconds(year + 1, 1),
                        f"{year}_daily"))
    return windows


def request_body(coin: str, kind: str, start: int, end: int) -> dict:
    if kind == "fundingHistory":
        return {"type": kind, "coin": coin, "startTime": start, "endTime": end}
    return {"type": kind, "req": {"coin": coin, "interval": "1d",
                                  "startTime": start, "endTime": end}}


def source_rows(output: Path, coin: str, kind: str, start: int, end: int,
                label: str) -> tuple[list[dict], dict]:
    name = f"{coin}_{label}_{kind}.json"
    path = output / name
    if path.exists():
        raw = path.read_bytes()
        payload = json.loads(raw)
    else:
        raw, payload = request_json(request_body(coin, kind, start, end))
        path.write_bytes(raw)
        time.sleep(1)
    if not isinstance(payload, list) or len(payload) >= 500:
        raise ValueError(f"invalid or possibly truncated time-range response: {name}")
    stamp_key = "time" if kind == "fundingHistory" else "t"
    selected = [row for row in payload if start <= int(row[stamp_key]) < end]
    stamps = [int(row[stamp_key]) for row in selected]
    slots = [stamp // (HOUR_MS if kind == "fundingHistory" else DAY_MS)
             * (HOUR_MS if kind == "fundingHistory" else DAY_MS) for stamp in stamps]
    if slots != sorted(set(slots)):
        raise ValueError(f"misordered or repeated slot: {name}")
    if any(row.get("coin" if kind == "fundingHistory" else "s") != coin
           for row in selected):
        raise ValueError(f"unexpected contract: {name}")
    if kind == "fundingHistory":
        if any(not -1 <= float(row["fundingRate"]) <= 1 for row in selected):
            raise ValueError(f"invalid funding rate: {name}")
    elif any(row.get("i") != "1d" or int(row["T"]) != int(row["t"]) + DAY_MS - 1
             or not (0 < float(row["l"]) <= min(float(row["o"]), float(row["c"]))
                     <= max(float(row["o"]), float(row["c"])) <= float(row["h"]))
             for row in selected):
        raise ValueError(f"invalid candle: {name}")
    return selected, {"source_key": name, "sha256": hashlib.sha256(raw).hexdigest(),
                      "raw_rows": len(payload), "selected_rows": len(selected)}


def audit(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    files = []
    coverage = []
    for coin in COINS:
        by_kind = {"fundingHistory": [], "candleSnapshot": []}
        for kind, start, end, label in periods():
            rows, source = source_rows(output, coin, kind, start, end, label)
            by_kind[kind].extend(rows)
            files.append({"coin": coin, **source})
        for kind, rows in by_kind.items():
            interval = HOUR_MS if kind == "fundingHistory" else DAY_MS
            stamp_key = "time" if kind == "fundingHistory" else "t"
            observed = {int(row[stamp_key]) // interval * interval for row in rows}
            expected = set(range(milliseconds(2024, 1), milliseconds(2026, 1), interval))
            if len(observed) != len(rows) or observed - expected:
                raise ValueError(f"duplicate or unexpected {kind} slot for {coin}")
            missing = sorted(expected - observed)
            coverage.append({"coin": coin, "kind": kind, "expected": len(expected),
                             "observed": len(observed), "missing": len(missing),
                             "first_missing_ms": missing[0] if missing else None,
                             "last_missing_ms": missing[-1] if missing else None})
    manifest = {"scope": "Hyperliquid BTC/ETH 2024-2025 source coverage only; no returns",
                "files": files, "coverage": coverage}
    (output / "coverage_report.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = audit(args.output)
    print(json.dumps(report["coverage"], indent=2))


if __name__ == "__main__":
    main()
