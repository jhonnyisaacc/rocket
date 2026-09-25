"""Normalize the hashed Bybit 2020-2022 source pages into a separate SQLite tape."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

from research.futures.bybit_eligibility import parse_funding, parse_prices
from research.futures.normalize_archives import initialize


def normalize(coverage_path: Path, raw_root: Path, database: Path) -> dict:
    manifest = json.loads(coverage_path.read_text())
    if manifest["failures"] or len(manifest["results"]) != manifest["candidate_count"]:
        raise ValueError("incomplete Bybit source inventory")
    if database.exists():
        raise ValueError("Bybit database already exists; use a new dataset version")
    db = sqlite3.connect(database)
    initialize(db)
    totals = Counter()
    try:
        for item in manifest["results"]:
            symbol = item["symbol"]
            sources = item["sources"]
            by_kind = {"daily": [], "funding": []}
            parsed_files = []
            for source in sources:
                key = source["key"]
                raw = (raw_root / key).read_bytes()
                if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                    raise ValueError(f"Bybit source hash changed: {key}")
                payload = json.loads(raw)
                rows = payload["result"]["list"]
                if len(rows) != source["rows"]:
                    raise ValueError(f"Bybit source row count changed: {key}")
                kind = "daily" if "_daily_" in key else "funding"
                by_kind[kind].extend(rows)
                if rows:
                    stamps = [int(row[0] if kind == "daily" else row["fundingRateTimestamp"])
                              for row in rows]
                    parsed_files.append((key, source["sha256"], len(rows),
                                         min(stamps), max(stamps), manifest["retrieved_at"]))
            eligibility_bars, anomalies = parse_prices(by_kind["daily"])
            funding = parse_funding(by_kind["funding"])
            funding_by_stamp = {record[0]: record for record in funding}
            price_rows = []
            funding_rows = []
            for source in sources:
                key = source["key"]
                rows = json.loads((raw_root / key).read_bytes())["result"]["list"]
                if "_daily_" in key:
                    for row in rows:
                        stamp = int(row[0])
                        open_, high, low, close, volume, turnover = map(float, row[1:])
                        price_rows.append((symbol, stamp, open_, high, low, close,
                                           volume, turnover, int(eligibility_bars[stamp][1]), key))
                else:
                    for row in rows:
                        stamp = int(row["fundingRateTimestamp"])
                        slot, _, interval, rate = funding_by_stamp[stamp]
                        funding_rows.append((symbol, slot, stamp, interval, rate, key))
            if len(price_rows) != item["price_days"] or len(funding_rows) != item["funding_rows"]:
                raise ValueError(f"Bybit normalized count mismatch: {symbol}")
            with db:
                db.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?,?)", price_rows)
                db.executemany("INSERT INTO funding VALUES (?,?,?,?,?,?)", funding_rows)
                db.executemany("INSERT INTO files VALUES (?,?,?,?,?,?)", parsed_files)
            totals["prices"] += len(price_rows)
            totals["funding"] += len(funding_rows)
            totals["source_pages"] += len(sources)
            totals["invalid_ohlc_bars"] += len(anomalies)
        return {"coverage_sha256": hashlib.sha256(coverage_path.read_bytes()).hexdigest(),
                **dict(totals)}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("raw_root", type=Path)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    print(json.dumps(normalize(args.coverage, args.raw_root, args.database), indent=2))


if __name__ == "__main__":
    main()
