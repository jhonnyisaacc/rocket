"""Acquire and audit FUT-006 source ZIPs; emit signals/proxies, never P&L.

This source preflight is deliberately separate from the scorer. It can resume
from checksum-verified ZIPs and records the entire day ID/timestamp audit,
while emitting only the two frozen signal and post-delay proxy windows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import time
import urllib.request
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

SYMBOLS = ("BTCUSDT", "ETHUSDT")
START = date(2024, 11, 1)
END = date(2025, 1, 1)  # End day supplies the final exit proxy only.
COLUMNS = ("agg_trade_id", "price", "quantity", "first_trade_id",
           "last_trade_id", "transact_time", "is_buyer_maker")
BASE = "https://data.binance.vision/data/futures/um/daily/aggTrades"


def days():
    day = START
    while day <= END:
        yield day
        day += timedelta(days=1)


def download(url: str, path: Path) -> None:
    if path.exists():
        return
    for attempt in range(4):
        temporary = path.with_name(path.name + ".part")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "rocket-fut006/1"})
            with urllib.request.urlopen(request, timeout=90) as src, temporary.open("wb") as dst:
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
            os.replace(temporary, path)
            return
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def ensure_archive(cache: Path, symbol: str, day: date) -> tuple[Path, str]:
    name = f"{symbol}-aggTrades-{day.isoformat()}.zip"
    folder = cache / symbol
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / name
    checksum_file = folder / (name + ".CHECKSUM")
    url = f"{BASE}/{symbol}/{name}"
    download(url + ".CHECKSUM", checksum_file)
    expected = checksum_file.read_text().split()
    if len(expected) != 2 or expected[1] != name or len(expected[0]) != 64:
        raise ValueError(f"bad official checksum: {name}")
    download(url, archive)
    with archive.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != expected[0]:
        archive.unlink()
        raise ValueError(f"ZIP checksum mismatch: {name}")
    return archive, digest


def audit_day(path: Path, day: date, symbol: str, digest: str) -> dict:
    start_ms = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)
    end_ms = start_ms + 86_400_000
    targets = (15 * 60_000, (12 * 60 + 15) * 60_000)
    windows = {offset: {"buy_qty": 0.0, "sell_qty": 0.0,
                        "signal_rows": 0, "proxy_price": None,
                        "proxy_ms": None} for offset in targets}
    with zipfile.ZipFile(path) as archive:
        expected_member = path.name.removesuffix(".zip") + ".csv"
        if archive.namelist() != [expected_member]:
            raise ValueError(f"bad ZIP member: {path.name}")
        with archive.open(expected_member) as handle:
            rows = csv.reader(io.TextIOWrapper(handle, encoding="utf-8-sig"))
            if tuple(next(rows)) != COLUMNS:
                raise ValueError(f"bad schema: {path.name}")
            first_id = last_id = first_ms = last_ms = None
            count = 0
            for row in rows:
                if len(row) != 7:
                    raise ValueError(f"bad row width: {path.name}")
                agg_id, price, qty, first_trade, last_trade, stamp, maker = row
                agg_id, stamp = int(agg_id), int(stamp)
                if not start_ms <= stamp < end_ms:
                    raise ValueError(f"out-of-day stamp: {path.name}")
                if last_id is not None and (agg_id != last_id + 1 or stamp < last_ms):
                    raise ValueError(f"ID/timestamp discontinuity: {path.name}")
                if int(first_trade) > int(last_trade) or maker not in ("true", "false"):
                    raise ValueError(f"bad trade IDs or side: {path.name}")
                if first_id is None:
                    first_id, first_ms = agg_id, stamp
                last_id, last_ms = agg_id, stamp
                count += 1
                offset = stamp - start_ms
                for target, window in windows.items():
                    if target <= offset < target + 10_000 and day < END:
                        quantity = float(qty)
                        if quantity <= 0:
                            raise ValueError(f"nonpositive signal quantity: {path.name}")
                        window["buy_qty" if maker == "false" else "sell_qty"] += quantity
                        window["signal_rows"] += 1
                    elif (target + 20_000 <= offset < target + 30_000
                          and window["proxy_price"] is None):
                        value = float(price)
                        if value <= 0:
                            raise ValueError(f"nonpositive proxy price: {path.name}")
                        window["proxy_price"] = value
                        window["proxy_ms"] = stamp
    if not count:
        raise ValueError(f"empty source: {path.name}")
    if any(w["proxy_price"] is None or (day < END and not w["signal_rows"])
           for w in windows.values()):
        raise ValueError(f"missing FUT-006 signal/proxy window: {path.name}")
    return {"symbol": symbol, "day": day.isoformat(), "sha256": digest,
            "bytes": path.stat().st_size, "rows": count, "first_id": first_id,
            "last_id": last_id, "first_ms": first_ms, "last_ms": last_ms,
            "windows": {f"{offset // 3_600_000:02d}:15": value
                        for offset, value in windows.items()}}


def acquire(cache: Path) -> dict:
    results = {}
    for symbol in SYMBOLS:
        previous = None
        entries = []
        for day in days():
            path, digest = ensure_archive(cache, symbol, day)
            record = audit_day(path, day, symbol, digest)
            if previous is not None and record["first_id"] != previous["last_id"] + 1:
                raise ValueError(f"cross-day aggregate ID gap: {symbol} {day}")
            entries.append(record)
            previous = record
            print(f"audited {symbol} {day} rows={record['rows']}", flush=True)
        results[symbol] = entries
    report = {"scope": "FUT-006 source audit, no forward returns",
              "freeze_commit": "cfb8916", "sources": results}
    output = cache / "fut006_source.json"
    output.write_text(json.dumps(report, separators=(",", ":")) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    args = parser.parse_args()
    acquire(args.cache)


if __name__ == "__main__":
    main()
