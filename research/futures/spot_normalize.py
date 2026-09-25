"""Normalize checksum-verified Binance spot 1d ZIPs into a separate SQLite tape.

Fail on missing or malformed raw data. Archive existence and normalized rows
do not establish point-in-time spot eligibility or a tradable basis signal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

from research.futures.spot_download import spot_key
from research.futures.spot_month_probe import parse_daily_rows


def initialize(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS files (
      source_key TEXT PRIMARY KEY, sha256 TEXT NOT NULL, rows INTEGER NOT NULL,
      first_ms INTEGER NOT NULL, last_ms INTEGER NOT NULL, retrieved_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS prices (
      symbol TEXT NOT NULL, open_ms INTEGER NOT NULL, open REAL NOT NULL,
      high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
      base_volume REAL NOT NULL, quote_volume REAL NOT NULL,
      close_ms INTEGER NOT NULL, complete_day INTEGER NOT NULL, tradable INTEGER NOT NULL,
      source_key TEXT NOT NULL, PRIMARY KEY(symbol, open_ms)
    );
    CREATE INDEX IF NOT EXISTS spot_prices_by_time ON prices(open_ms);
    """)


def normalize(inventory: dict, raw_root: Path, database: Path) -> dict:
    records = {}
    for line in (raw_root / "acquisition.jsonl").read_text().splitlines():
        record = json.loads(line)
        records[record["key"]] = record
    tasks = [(symbol, month) for symbol, months in sorted(inventory["spot_months"].items())
             for month in months]
    database.parent.mkdir(parents=True, exist_ok=True)
    counts = defaultdict(int)
    failures = []
    with sqlite3.connect(database) as db:
        initialize(db)
        for index, (symbol, month) in enumerate(tasks, start=1):
            key = spot_key(symbol, month)
            record = records.get(key)
            path = raw_root / key
            if record is None or not path.exists():
                raise ValueError(f"missing acquired spot archive: {key}")
            existing = db.execute("SELECT sha256 FROM files WHERE source_key=?", (key,)).fetchone()
            if existing is not None:
                if existing[0] != record["sha256"]:
                    raise ValueError(f"spot source revision requires new version: {key}")
                continue
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != record["sha256"]:
                raise ValueError(f"spot archive hash changed: {key}")
            try:
                rows = parse_daily_rows(raw, int(month[:4]))
            except ValueError as exc:
                failures.append({"source_key": key, "reason": str(exc)})
                continue
            if any(datetime.fromtimestamp(row[0] / 1000, UTC).strftime("%Y-%m") != month
                   for row in rows):
                failures.append({"source_key": key, "reason": "spot row outside source month"})
                continue
            try:
                with db:
                    db.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                                   [(symbol, *row, key) for row in rows])
                    db.execute("INSERT INTO files VALUES (?,?,?,?,?,?)",
                               (key, record["sha256"], len(rows), rows[0][0], rows[-1][0],
                                record["retrieved_at"]))
            except sqlite3.IntegrityError as exc:
                failures.append({"source_key": key, "reason": f"SQLite integrity error: {exc}"})
                continue
            counts["new_files"] += 1
            counts["new_rows"] += len(rows)
            counts["new_nontradable_rows"] += sum(not row[-1] for row in rows)
            counts["new_partial_days"] += sum(not row[-2] for row in rows)
            counts["new_internal_gaps"] += sum(right[0] - left[0] != 86_400_000
                                               for left, right in pairwise(rows))
            if index % 1000 == 0:
                print(f"normalized {index}/{len(tasks)} spot archives", file=sys.stderr, flush=True)
        counts["expected_files"] = len(tasks)
        counts["total_files"] = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        counts["total_prices"] = db.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        counts["total_nontradable"] = db.execute("SELECT COUNT(*) FROM prices WHERE tradable=0").fetchone()[0]
        counts["total_partial_days"] = db.execute("SELECT COUNT(*) FROM prices WHERE complete_day=0").fetchone()[0]
        counts["normalized_at"] = datetime.now(UTC).isoformat()
    return {**counts, "failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("raw_root", type=Path)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    summary = normalize(json.loads(args.inventory.read_text()), args.raw_root, args.database)
    print(json.dumps(summary, indent=2))
    if summary["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
