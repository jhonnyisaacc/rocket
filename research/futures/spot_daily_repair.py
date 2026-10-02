"""Replace one malformed spot monthly ZIP with checksum-verified daily ZIPs.

The failed monthly source stays preserved in the raw archive directory and is
named in the repair report. Missing daily keys remain missing; no fill is made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from research.futures.archive_coverage import list_keys
from research.futures.download_archives import BASE, fetch
from research.futures.spot_month_probe import parse_daily_rows
from research.futures.spot_source_audit import SPOT_ROOT


def daily_keys(symbol: str, month: str) -> list[str]:
    prefix = f"data/spot/daily/klines/{symbol}/1d/"
    stem = f"{symbol}-1d-{month}-"
    return sorted(key for key in list_keys(prefix)
                  if key.startswith(prefix + stem) and key.endswith(".zip"))


def checked_day(key: str, symbol: str, month: str) -> tuple[bytes, dict, tuple | None, str | None]:
    url = BASE + urllib.parse.quote(key, safe="/")
    checksum = fetch(url + ".CHECKSUM").decode("utf-8").strip().split()
    if len(checksum) != 2 or checksum[1] != Path(key).name:
        raise ValueError(f"malformed daily checksum: {key}")
    raw = fetch(url)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != checksum[0].lower():
        raise ValueError(f"daily checksum mismatch: {key}")
    try:
        rows = parse_daily_rows(raw, int(month[:4]))
    except ValueError as exc:
        rows = []
        error = str(exc)
    else:
        error = None
    if rows and (len(rows) != 1 or datetime.fromtimestamp(rows[0][0] / 1000, UTC).strftime("%Y-%m") != month):
        rows = []
        error = "unexpected daily rows"
    record = {"key": key, "symbol": symbol, "sha256": digest,
              "bytes": len(raw), "retrieved_at": datetime.now(UTC).isoformat()}
    return raw, record, rows[0] if rows else None, error


def repair(database: Path, raw_root: Path, symbol: str, month: str,
           *, workers: int = 12) -> dict:
    failed_month = f"{SPOT_ROOT}{symbol}/1d/{symbol}-1d-{month}.zip"
    keys = daily_keys(symbol, month)
    if not keys:
        raise ValueError(f"no daily archives for {symbol} {month}")
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(checked_day, key, symbol, month): key for key in keys}
        for future in as_completed(jobs):
            results[jobs[future]] = future.result()
    good_keys = [key for key in keys if results[key][2] is not None]
    stamps = [results[key][2][0] for key in good_keys]
    if not stamps:
        raise ValueError("all daily sources are malformed")
    if len(stamps) != len(set(stamps)) or stamps != sorted(stamps):
        raise ValueError("duplicate or unsorted daily source days")
    for key in keys:
        raw, _, _, _ = results[key]
        path = raw_root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    with sqlite3.connect(database) as db:
        if db.execute("SELECT 1 FROM files WHERE source_key=?", (failed_month,)).fetchone():
            raise ValueError("monthly source was already accepted")
        if db.execute("SELECT 1 FROM prices WHERE symbol=? AND open_ms BETWEEN ? AND ? LIMIT 1",
                      (symbol, stamps[0], stamps[-1])).fetchone():
            raise ValueError("daily replacement would overlap existing rows")
        with db:
            for key in good_keys:
                _, record, row, _ = results[key]
                db.execute("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           (symbol, *row, key))
                db.execute("INSERT INTO files VALUES (?,?,?,?,?,?)",
                           (key, record["sha256"], 1, row[0], row[0], record["retrieved_at"]))
    report = {"failed_monthly_source": failed_month,
              "reason": "mixed timestamp units and invalid final close in checksum-valid monthly ZIP",
              "verified_daily_files": len(keys), "accepted_daily_rows": len(good_keys),
              "quarantined_daily_files": [{"key": key, "reason": results[key][3]}
                                          for key in keys if results[key][2] is None],
              "partial_days": sum(not results[key][2][-2] for key in good_keys),
              "sources": [results[key][1] for key in keys],
              "meaning": "separate daily-source version; invalid and absent days remain missing"}
    (raw_root / f"{symbol}-{month}-daily-repair.json").write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("raw_root", type=Path)
    parser.add_argument("symbol")
    parser.add_argument("month")
    args = parser.parse_args()
    print(json.dumps(repair(args.database, args.raw_root, args.symbol, args.month), indent=2))


if __name__ == "__main__":
    main()
