"""Checksum and schema probe of selected Binance monthly spot 1d archives.

Run: python -m research.futures.spot_month_probe OUTPUT_DIR
This checks source integrity and timestamps only; it never computes a basis or return.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

from research.futures.archive_catalog import ENDPOINT

MONTHS = (("BTCUSDT", "2024-01"), ("ETHUSDT", "2024-01"),
          ("BTCUSDT", "2025-01"), ("ETHUSDT", "2025-01"))
DAY_MS = 86_400_000


def parse_daily(raw: bytes, year: int) -> dict:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != 1 or not names[0].endswith(".csv"):
            raise ValueError("expected one CSV in spot archive")
        rows = list(csv.reader(io.TextIOWrapper(archive.open(names[0]), encoding="utf-8-sig")))
    if rows and rows[0][0].lower().replace(" ", "_") == "open_time":
        rows = rows[1:]
    if not rows:
        raise ValueError("no spot rows")
    stamps = []
    for row in rows:
        if len(row) != 12:
            raise ValueError("unexpected spot row width")
        open_raw, close_raw = int(row[0]), int(row[6])
        divisor = 1000 if year >= 2025 else 1
        expected_digits = 16 if year >= 2025 else 13
        if len(row[0]) != expected_digits or len(row[6]) != expected_digits:
            raise ValueError("unexpected spot timestamp units")
        if (open_raw % divisor != 0 or (close_raw + 1) % divisor != 0
                or close_raw != open_raw + DAY_MS * divisor - 1):
            raise ValueError("invalid spot daily interval")
        stamp = open_raw // divisor
        if stamp % DAY_MS:
            raise ValueError("spot day not UTC aligned")
        open_, high, low, close = (float(row[index]) for index in (1, 2, 3, 4))
        base_volume, quote_volume = float(row[5]), float(row[7])
        if not (0 < low <= min(open_, close) <= max(open_, close) <= high
                and base_volume >= 0 and quote_volume >= 0):
            raise ValueError("invalid spot OHLC or volume")
        stamps.append(stamp)
    if stamps != sorted(set(stamps)):
        raise ValueError("duplicate or unsorted spot days")
    if any(right - left != DAY_MS for left, right in pairwise(stamps)):
        raise ValueError("spot month has a daily gap")
    return {"rows": len(rows), "first_day": datetime.fromtimestamp(stamps[0] / 1000, UTC).date().isoformat(),
            "last_day": datetime.fromtimestamp(stamps[-1] / 1000, UTC).date().isoformat(),
            "timestamp_unit": "microseconds" if year >= 2025 else "milliseconds"}


def fetch(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "rocket-spot-month-probe/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def probe(output: Path, *, timeout: float = 20.0) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    files = []
    for symbol, month in MONTHS:
        name = f"{symbol}-1d-{month}.zip"
        key = f"data/spot/monthly/klines/{symbol}/1d/{name}"
        raw = fetch(f"{ENDPOINT}/{key}", timeout)
        sidecar = fetch(f"{ENDPOINT}/{key}.CHECKSUM", timeout).decode().strip()
        expected = sidecar.split()[0]
        actual = hashlib.sha256(raw).hexdigest()
        if expected != actual:
            raise ValueError(f"checksum mismatch for {key}")
        parsed = parse_daily(raw, int(month[:4]))
        (output / name).write_bytes(raw)
        files.append({"source_key": key, "sha256": actual, **parsed})
    return {"retrieved_at": datetime.now(UTC).isoformat(), "source": ENDPOINT,
            "meaning": "four selected files only; no broad monthly or PIT coverage claim", "files": files}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    print(json.dumps(probe(args.output, timeout=args.timeout), indent=2))


if __name__ == "__main__":
    main()
