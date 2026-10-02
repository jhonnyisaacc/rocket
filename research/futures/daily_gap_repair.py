"""Fill an observed monthly-archive gap from checksum-verified daily ZIPs.

Writes only a separately versioned research database. Both neighboring daily
bars must exist and be tradable; every missing day must have a verified source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from research.futures.download_archives import BASE, fetch
from research.futures.normalize_archives import DAY_MS, parse_prices


def day_ms(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)


def gap_tasks(db: sqlite3.Connection, first: date, last: date) -> list[tuple[str, date]]:
    if first > last:
        raise ValueError("empty gap")
    before = day_ms(first) - DAY_MS
    after = day_ms(last) + DAY_MS
    symbols = [row[0] for row in db.execute(
        "SELECT symbol FROM prices WHERE open_ms=? AND tradable=1 "
        "INTERSECT SELECT symbol FROM prices WHERE open_ms=? AND tradable=1 ORDER BY symbol",
        (before, after))]
    tasks = []
    for symbol in symbols:
        day = first
        while day <= last:
            if db.execute("SELECT 1 FROM prices WHERE symbol=? AND open_ms=?",
                          (symbol, day_ms(day))).fetchone() is None:
                tasks.append((symbol, day))
            day += timedelta(days=1)
    return tasks


def daily_key(symbol: str, day: date) -> str:
    stamp = day.isoformat()
    return f"data/futures/um/daily/klines/{symbol}/1d/{symbol}-1d-{stamp}.zip"


def checked_daily(symbol: str, day: date, output: Path) -> tuple[dict, tuple]:
    key = daily_key(symbol, day)
    url = BASE + urllib.parse.quote(key, safe="/")
    checksum = fetch(url + ".CHECKSUM").decode("utf-8").strip().split()
    if len(checksum) != 2 or checksum[1] != Path(key).name:
        raise ValueError(f"malformed daily checksum: {key}")
    raw = fetch(url)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != checksum[0].lower():
        raise ValueError(f"daily checksum mismatch: {key}")
    rows = parse_prices(raw)
    if len(rows) != 1 or rows[0][0] != day_ms(day) or not rows[0][-1]:
        raise ValueError(f"daily repair not a valid active bar: {key}")
    path = output / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    record = {"key": key, "symbol": symbol, "date": day.isoformat(),
              "sha256": digest, "bytes": len(raw), "source": url,
              "retrieved_at": datetime.now(UTC).isoformat()}
    return record, rows[0]


def repair(database: Path, output: Path, first: date, last: date,
           *, workers: int = 16) -> dict:
    db = sqlite3.connect(database)
    try:
        tasks = gap_tasks(db, first, last)
        results = {}
        failures = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(checked_daily, symbol, day, output): (symbol, day)
                       for symbol, day in tasks}
            for future in as_completed(futures):
                symbol, day = futures[future]
                try:
                    results[(symbol, day)] = future.result()
                except Exception as exc:
                    failures.append({"symbol": symbol, "date": day.isoformat(), "error": str(exc)})
        if failures:
            raise ValueError(f"daily source failures: {json.dumps(failures, sort_keys=True)}")
        with db:
            for symbol, day in sorted(results):
                record, bar = results[(symbol, day)]
                db.execute("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (symbol, *bar, record["key"]))
                db.execute("INSERT INTO files VALUES (?,?,?,?,?,?)",
                           (record["key"], record["sha256"], 1,
                            bar[0], bar[0], record["retrieved_at"]))
        report = {"meaning": "verified daily repair of missing monthly rows",
                  "database": str(database), "first": first.isoformat(), "last": last.isoformat(),
                  "repaired_rows": len(results),
                  "sources": [results[key][0] for key in sorted(results)]}
        output.mkdir(parents=True, exist_ok=True)
        (output / "daily_gap_repair.json").write_text(json.dumps(report, indent=2))
        return report
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("first", type=date.fromisoformat)
    parser.add_argument("last", type=date.fromisoformat)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    report = repair(args.database, args.output, args.first, args.last, workers=args.workers)
    print(json.dumps({"repaired_rows": report["repaired_rows"],
                      "report": str(args.output / "daily_gap_repair.json")}, indent=2))


if __name__ == "__main__":
    main()
