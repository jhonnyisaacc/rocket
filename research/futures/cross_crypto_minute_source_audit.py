"""Checksum and clock audit of fixed BTC spot / ETH,SOL perp minute archives.

This source-only check does not compute returns or select signal events.
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile


BASE = "https://data.binance.vision/"
MONTHS = ("2024-11", "2025-04", "2025-08")
SOURCES = (("spot", "BTCUSDT"), ("futures/um", "ETHUSDT"),
           ("futures/um", "SOLUSDT"))
MINUTE_MS = 60_000


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "rocket-lead-lag-source/1"}),
        timeout=60,
    ) as response:
        return response.read()


def source_key(market: str, symbol: str, month: str) -> str:
    return (f"data/{market}/monthly/klines/{symbol}/1m/"
            f"{symbol}-1m-{month}.zip")


def audit_zip(raw: bytes, month: str) -> tuple[dict, set[int]]:
    year, month_number = (int(value) for value in month.split("-"))
    start = int(datetime(year, month_number, 1, tzinfo=UTC).timestamp() * 1000)
    next_year, next_month = divmod(month_number, 12)
    end = int(datetime(year + next_year, next_month + 1, 1, tzinfo=UTC).timestamp() * 1000)
    counts = {"rows": 0, "zero_base_volume": 0, "zero_quote_volume": 0}
    stamps: set[int] = set()
    unit: int | None = None
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != 1 or not names[0].endswith(".csv"):
            raise ValueError("expected one CSV member")
        with archive.open(names[0]) as member:
            reader = csv.reader(io.TextIOWrapper(member, encoding="utf-8-sig"))
            for row in reader:
                if row and row[0].lower().replace(" ", "_") == "open_time":
                    continue
                if len(row) != 12:
                    raise ValueError("unexpected Binance minute kline width")
                current_unit = 1000 if len(row[0]) == 16 else 1 if len(row[0]) == 13 else 0
                if current_unit == 0 or (unit is not None and current_unit != unit):
                    raise ValueError("inconsistent source timestamp units")
                unit = current_unit
                open_raw, close_raw = int(row[0]), int(row[6])
                if open_raw % unit or close_raw != open_raw + MINUTE_MS * unit - 1:
                    raise ValueError("invalid minute interval or sub-ms alignment")
                stamp = open_raw // unit
                if not start <= stamp < end or stamp % MINUTE_MS or stamp in stamps:
                    raise ValueError("duplicate, off-grid or out-of-month minute")
                open_, high, low, close = (float(row[index]) for index in (1, 2, 3, 4))
                base_volume, quote_volume = float(row[5]), float(row[7])
                if not (0 < low <= min(open_, close) <= max(open_, close) <= high
                        and base_volume >= 0 and quote_volume >= 0):
                    raise ValueError("invalid OHLC or volume")
                stamps.add(stamp)
                counts["rows"] += 1
                counts["zero_base_volume"] += int(base_volume == 0)
                counts["zero_quote_volume"] += int(quote_volume == 0)
    expected = set(range(start, end, MINUTE_MS))
    counts.update({
        "expected_minutes": len(expected),
        "missing_minutes": len(expected - stamps),
        "first_ms": min(stamps) if stamps else None,
        "last_ms": max(stamps) if stamps else None,
        "timestamp_unit": "microseconds" if unit == 1000 else "milliseconds",
    })
    return counts, stamps


def audit(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    files = []
    overlap = {}
    for month in MONTHS:
        clocks = []
        for market, symbol in SOURCES:
            key = source_key(market, symbol, month)
            path = output / key
            checksum_path = output / (key + ".CHECKSUM")
            if path.exists() and checksum_path.exists():
                raw = path.read_bytes()
                sidecar = checksum_path.read_bytes()
            else:
                raw = fetch(BASE + key)
                sidecar = fetch(BASE + key + ".CHECKSUM")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                checksum_path.write_bytes(sidecar)
            tokens = sidecar.decode().strip().split()
            digest = hashlib.sha256(raw).hexdigest()
            if len(tokens) != 2 or tokens[0].lower() != digest or tokens[1] != path.name:
                raise ValueError(f"published checksum mismatch: {key}")
            counts, stamps = audit_zip(raw, month)
            clocks.append(stamps)
            files.append({"source_key": key, "sha256": digest, "bytes": len(raw),
                          "checksum_sha256": hashlib.sha256(sidecar).hexdigest(), **counts})
        overlap[month] = {
            "all_three_common_minutes": len(set.intersection(*clocks)),
            "all_three_union_minutes": len(set.union(*clocks)),
        }
    return {"meaning": "source-only 1m integrity and common-clock audit; no return read",
            "retrieved_at": datetime.now(UTC).isoformat(), "files": files,
            "clock_overlap": overlap}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = audit(args.output)
    (args.output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
