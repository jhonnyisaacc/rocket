"""Normalize checksum-verified futures archives to SQLite with strict row checks.

Raw archives remain the source of truth. This tool accepts only files named in
the acquisition log, checks their recorded hashes again, and fails on any
missing, malformed, duplicate or time-misaligned row. A flat/zero-volume bar
is retained but marked ineligible; it is not silently discarded.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sqlite3
import sys
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from research.futures.download_archives import archive_key, tasks_from_coverage

DAY_MS = 86_400_000
HOUR_MS = 3_600_000
PRICE_COLUMNS = ("open_time", "open", "high", "low", "close", "volume",
                 "close_time", "quote_volume", "count", "taker_buy_volume",
                 "taker_buy_quote_volume", "ignore")
FUNDING_COLUMNS = ("calc_time", "funding_interval_hours", "last_funding_rate")


def csv_rows(raw: bytes, *, kind: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != 1 or not names[0].endswith(".csv"):
            raise ValueError("archive must contain one CSV")
        lines = list(csv.reader(io.TextIOWrapper(archive.open(names[0]), encoding="utf-8-sig")))
    if not lines:
        raise ValueError("empty archive CSV")
    columns = PRICE_COLUMNS if kind == "klines" else FUNDING_COLUMNS
    first = [cell.strip() for cell in lines[0]]
    if first == list(columns):
        lines = lines[1:]
    elif len(first) != len(columns) or not first[0].isdigit():
        raise ValueError("unexpected archive header")
    if not lines:
        raise ValueError("no data rows")
    if any(len(row) != len(columns) for row in lines):
        raise ValueError("inconsistent CSV row width")
    return [dict(zip(columns, row, strict=True)) for row in lines]


def parse_prices(raw: bytes) -> list[tuple]:
    parsed = []
    seen = set()
    for row in csv_rows(raw, kind="klines"):
        stamp = int(row["open_time"])
        close_stamp = int(row["close_time"])
        if stamp < 1_500_000_000_000 or stamp % DAY_MS or close_stamp != stamp + DAY_MS - 1:
            raise ValueError(f"invalid daily timestamp {stamp}")
        if stamp in seen:
            raise ValueError(f"duplicate daily timestamp {stamp}")
        seen.add(stamp)
        open_, high, low, close = (float(row[name]) for name in ("open", "high", "low", "close"))
        volume, quote = float(row["volume"]), float(row["quote_volume"])
        if not (0 < low <= min(open_, close) <= max(open_, close) <= high
                and volume >= 0 and quote >= 0):
            raise ValueError(f"invalid OHLC or volume at {stamp}")
        tradable = int(volume > 0 and quote > 0 and high > low)
        parsed.append((stamp, open_, high, low, close, volume, quote, tradable))
    return sorted(parsed)


def parse_funding(raw: bytes) -> list[tuple]:
    parsed = []
    seen = set()
    for row in csv_rows(raw, kind="fundingRate"):
        stamp = int(row["calc_time"])
        slot = stamp // HOUR_MS * HOUR_MS
        interval = int(row["funding_interval_hours"])
        rate = float(row["last_funding_rate"])
        if stamp < 1_500_000_000_000 or stamp-slot > 60_000 or not 1 <= interval <= 24:
            raise ValueError(f"invalid funding timestamp/interval {stamp}")
        if not -1 <= rate <= 1:
            raise ValueError(f"invalid funding rate {stamp}")
        if slot in seen:
            raise ValueError(f"duplicate funding hour {slot}")
        seen.add(slot)
        parsed.append((slot, stamp, interval, rate))
    return sorted(parsed)


def initialize(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS files (
      source_key TEXT PRIMARY KEY, sha256 TEXT NOT NULL, rows INTEGER NOT NULL,
      first_ms INTEGER NOT NULL, last_ms INTEGER NOT NULL, retrieved_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS prices (
      symbol TEXT NOT NULL, open_ms INTEGER NOT NULL, open REAL NOT NULL,
      high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
      base_volume REAL NOT NULL, quote_volume REAL NOT NULL, tradable INTEGER NOT NULL,
      source_key TEXT NOT NULL, PRIMARY KEY(symbol, open_ms)
    );
    CREATE TABLE IF NOT EXISTS funding (
      symbol TEXT NOT NULL, slot_ms INTEGER NOT NULL, stamp_ms INTEGER NOT NULL,
      interval_hours INTEGER NOT NULL, rate REAL NOT NULL, source_key TEXT NOT NULL,
      PRIMARY KEY(symbol, slot_ms)
    );
    CREATE INDEX IF NOT EXISTS prices_by_time ON prices(open_ms);
    CREATE INDEX IF NOT EXISTS funding_by_time ON funding(slot_ms);
    """)


def normalize(coverage: dict, raw_root: Path, database: Path, *, start_year: int,
              end_year: int, selected: set[str] | None = None) -> dict:
    records = {}
    for line in (raw_root / "acquisition.jsonl").read_text().splitlines():
        record = json.loads(line)
        records[record["key"]] = record
    tasks = tasks_from_coverage(coverage, start_year, end_year, selected)
    database.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(database)
    initialize(db)
    counts = defaultdict(int)
    try:
        for index, (symbol, kind, month) in enumerate(tasks, start=1):
            key = archive_key(symbol, kind, month)
            record = records.get(key)
            path = raw_root / key
            if record is None or not path.exists():
                raise ValueError(f"missing acquired archive: {key}")
            existing = db.execute("SELECT sha256 FROM files WHERE source_key=?", (key,)).fetchone()
            if existing is not None:
                if existing[0] != record["sha256"]:
                    raise ValueError(f"source revision requires a new dataset version: {key}")
                continue
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != record["sha256"]:
                raise ValueError(f"local archive hash changed: {key}")
            parsed = parse_prices(raw) if kind == "klines" else parse_funding(raw)
            with db:
                if kind == "klines":
                    db.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?,?)",
                                   [(symbol, *row, key) for row in parsed])
                    counts["nontradable_bars"] += sum(not row[-1] for row in parsed)
                else:
                    db.executemany("INSERT INTO funding VALUES (?,?,?,?,?,?)",
                                   [(symbol, *row, key) for row in parsed])
                db.execute("INSERT INTO files VALUES (?,?,?,?,?,?)",
                           (key, record["sha256"], len(parsed), parsed[0][0],
                            parsed[-1][0], record["retrieved_at"]))
            counts[kind + "_files"] += 1
            counts[kind + "_rows"] += len(parsed)
            if index % 1000 == 0:
                print(f"normalized {index}/{len(tasks)} archives", file=sys.stderr, flush=True)
        counts["expected_files"] = len(tasks)
        counts["total_files"] = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        counts["total_prices"] = db.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        counts["total_funding"] = db.execute("SELECT COUNT(*) FROM funding").fetchone()[0]
        counts["normalized_at"] = datetime.now(UTC).isoformat()
        return dict(counts)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("raw_root", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--symbols")
    args = parser.parse_args()
    selected = set(args.symbols.split(",")) if args.symbols else None
    print(json.dumps(normalize(json.loads(args.coverage.read_text()), args.raw_root,
                               args.database, start_year=args.start_year,
                               end_year=args.end_year, selected=selected), indent=2))


if __name__ == "__main__":
    main()
