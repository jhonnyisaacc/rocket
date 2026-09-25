"""Audit ETH hourly Binance USD-M candles and 8-hour funding, without returns.

The output records only source integrity and temporal coverage. All price
values remain in checksum-verified ZIPs until a separate rule is frozen.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import io
import json
import os
import sqlite3
import time
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

SYMBOL = "ETHUSDT"
YEARS = (2023, 2024, 2025)
BASE = f"https://data.binance.vision/data/futures/um/monthly/klines/{SYMBOL}/1h"
DB_SHA = "e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b"
COLUMNS = ("open_time", "open", "high", "low", "close", "volume", "close_time",
           "quote_volume", "count", "taker_buy_volume",
           "taker_buy_quote_volume", "ignore")
HOUR_MS = 3_600_000


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def fetch(url: str, path: Path) -> None:
    if path.exists():
        return
    for attempt in range(4):
        part = path.with_name(path.name + ".part")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "rocket-funding-source/1"})
            with urllib.request.urlopen(request, timeout=45) as src, part.open("wb") as dst:
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
            os.replace(part, path)
            return
        except Exception:
            part.unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def audit_month(folder: Path, year: int, month: int) -> dict:
    name = f"{SYMBOL}-1h-{year}-{month:02d}.zip"
    path = folder / name
    checksum = folder / (name + ".CHECKSUM")
    fetch(f"{BASE}/{name}.CHECKSUM", checksum)
    expected = checksum.read_text().split()
    if len(expected) != 2 or expected[1] != name or len(expected[0]) != 64:
        raise ValueError(f"bad official checksum: {name}")
    fetch(f"{BASE}/{name}", path)
    digest = sha256(path)
    if digest != expected[0]:
        path.unlink()
        raise ValueError(f"ZIP checksum mismatch: {name}")
    start = int(datetime(year, month, 1, tzinfo=UTC).timestamp() * 1000)
    count = 0
    with zipfile.ZipFile(path) as archive:
        member = name.removesuffix(".zip") + ".csv"
        if archive.namelist() != [member]:
            raise ValueError(f"bad ZIP layout: {name}")
        with archive.open(member) as handle:
            reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8-sig"))
            if tuple(next(reader)) != COLUMNS:
                raise ValueError(f"bad hourly schema: {name}")
            for row in reader:
                if len(row) != len(COLUMNS):
                    raise ValueError(f"bad row width: {name}")
                opening = int(row[0])
                if opening != start + count * HOUR_MS or int(row[6]) != opening + HOUR_MS - 1:
                    raise ValueError(f"hourly gap or close-time mismatch: {name} row {count}")
                open_, high, low, close = map(float, row[1:5])
                if low <= 0 or not low <= open_ <= high or not low <= close <= high:
                    raise ValueError(f"invalid OHLC: {name} row {count}")
                count += 1
    expected_rows = calendar.monthrange(year, month)[1] * 24
    if count != expected_rows:
        raise ValueError(f"incomplete month: {name} {count}/{expected_rows}")
    return {"source_key": name, "sha256": digest, "bytes": path.stat().st_size,
            "rows": count, "first_open_ms": start,
            "last_open_ms": start + (count - 1) * HOUR_MS}


def audit_funding(database: Path) -> dict:
    if sha256(database) != DB_SHA:
        raise ValueError("normalized funding database fingerprint changed")
    output = {}
    with sqlite3.connect(database) as db:
        for year in YEARS:
            start = int(datetime(year, 1, 1, tzinfo=UTC).timestamp() * 1000)
            end = int(datetime(year + 1, 1, 1, tzinfo=UTC).timestamp() * 1000)
            rows = list(db.execute(
                "SELECT slot_ms,stamp_ms,interval_hours FROM funding "
                "WHERE symbol=? AND slot_ms>=? AND slot_ms<? ORDER BY slot_ms",
                (SYMBOL, start, end)))
            expected = (end - start) // (8 * HOUR_MS)
            if len(rows) != expected or any(
                slot != start + index * 8 * HOUR_MS or not slot <= stamp < slot + HOUR_MS or interval != 8
                for index, (slot, stamp, interval) in enumerate(rows)):
                raise ValueError(f"funding cadence or timestamp mismatch: {year}")
            output[str(year)] = {"slots": len(rows), "first_slot_ms": rows[0][0],
                                 "last_slot_ms": rows[-1][0],
                                 "max_stamp_after_slot_ms": max(stamp - slot for slot, stamp, _ in rows)}
    return {"database_sha256": DB_SHA, "coverage": output}


def audit(folder: Path, database: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    funding = audit_funding(database)
    files = []
    for year in YEARS:
        for month in range(1, 13):
            item = audit_month(folder, year, month)
            files.append(item)
            print(f"audited {item['source_key']} rows={item['rows']}", flush=True)
    report = {"scope": "ETH 2023-2025 hourly candle/funding source only; no returns",
              "files": files, "funding": funding}
    (folder / "source_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("funding_database", type=Path)
    args = parser.parse_args()
    audit(args.folder, args.funding_database)


if __name__ == "__main__":
    main()
