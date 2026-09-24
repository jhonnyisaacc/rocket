"""Acquire and audit BTCUSDT hourly Binance archives for a macro source gate.

This checks source integrity, price continuity and funding coverage only.
No dollar-conditioned BTC return or trade outcome is computed.
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
from datetime import datetime, timezone
from pathlib import Path


SYMBOL = "BTCUSDT"
YEARS = (2022, 2023, 2024, 2025)
BASE = f"https://data.binance.vision/data/futures/um/monthly/klines/{SYMBOL}/1h"
FUNDING_DB_SHA256 = "e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b"
COLUMNS = ("open_time", "open", "high", "low", "close", "volume", "close_time",
           "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore")
HOUR_MS = 3_600_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str, path: Path) -> None:
    if path.exists():
        return
    for attempt in range(4):
        part = path.with_name(path.name + ".part")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "rocket-macro-source/1"})
            with urllib.request.urlopen(request, timeout=60) as source, part.open("wb") as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    target.write(chunk)
            os.replace(part, path)
            return
        except Exception:
            part.unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def audit_month(folder: Path, year: int, month: int) -> dict:
    name = f"{SYMBOL}-1h-{year}-{month:02d}.zip"
    archive_path = folder / name
    checksum_path = folder / (name + ".CHECKSUM")
    fetch(f"{BASE}/{name}.CHECKSUM", checksum_path)
    expected = checksum_path.read_text().strip().split()
    if len(expected) != 2 or expected[1] != name or len(expected[0]) != 64:
        raise ValueError(f"invalid official checksum sidecar: {name}")
    fetch(f"{BASE}/{name}", archive_path)
    digest = sha256(archive_path)
    if digest != expected[0]:
        archive_path.unlink()
        raise ValueError(f"ZIP checksum mismatch: {name}")
    start = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)
    count = 0
    with zipfile.ZipFile(archive_path) as archive:
        member = name[:-4] + ".csv"
        if archive.namelist() != [member]:
            raise ValueError(f"unexpected ZIP member: {name}")
        with archive.open(member) as handle:
            reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8-sig"))
            if tuple(next(reader)) != COLUMNS:
                raise ValueError(f"unexpected candle schema: {name}")
            for row in reader:
                if len(row) != len(COLUMNS):
                    raise ValueError(f"unexpected candle width: {name}")
                stamp = int(row[0])
                if stamp != start + count * HOUR_MS or int(row[6]) != stamp + HOUR_MS - 1:
                    raise ValueError(f"hourly gap or clock mismatch: {name} row {count}")
                opening, high, low, close = map(float, row[1:5])
                if low <= 0 or not low <= opening <= high or not low <= close <= high:
                    raise ValueError(f"invalid OHLC: {name} row {count}")
                count += 1
    expected_rows = calendar.monthrange(year, month)[1] * 24
    if count != expected_rows:
        raise ValueError(f"incomplete month: {name} {count}/{expected_rows}")
    return {"source_key": name, "sha256": digest, "bytes": archive_path.stat().st_size,
            "rows": count, "first_open_ms": start,
            "last_open_ms": start + (count - 1) * HOUR_MS}


def audit_funding(database: Path) -> dict:
    if sha256(database) != FUNDING_DB_SHA256:
        raise ValueError("funding database fingerprint mismatch")
    result = {}
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        for year in YEARS:
            start = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
            end = int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
            slots = list(connection.execute(
                "SELECT slot_ms,stamp_ms,interval_hours FROM funding "
                "WHERE symbol=? AND slot_ms>=? AND slot_ms<? ORDER BY slot_ms",
                (SYMBOL, start, end)))
            expected = (end - start) // (8 * HOUR_MS)
            if len(slots) != expected or any(
                slot != start + index * 8 * HOUR_MS or not slot <= stamp < slot + HOUR_MS or hours != 8
                for index, (slot, stamp, hours) in enumerate(slots)
            ):
                raise ValueError(f"funding gap or timestamp mismatch: {year}")
            result[str(year)] = {"slots": len(slots), "first_slot_ms": slots[0][0],
                                 "last_slot_ms": slots[-1][0]}
    return {"database_sha256": FUNDING_DB_SHA256, "by_year": result}


def audit(folder: Path, database: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    funding = audit_funding(database)
    files = []
    for year in YEARS:
        for month in range(1, 13):
            item = audit_month(folder, year, month)
            files.append(item)
            print(f"audited {item['source_key']} rows={item['rows']}", flush=True)
    report = {"scope": "BTCUSDT 2022-2025 hourly candles and funding source only",
              "no_signal_outcome_read": True, "files": files, "funding": funding}
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
