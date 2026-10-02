"""Inventory Binance spot 1d ZIP months against observed futures bar months.

File presence is a source coverage bound, never point-in-time eligibility.
Run: python -m research.futures.spot_month_inventory SPOT_AUDIT.json FUTURES.sqlite
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from research.futures.archive_catalog import ENDPOINT
from research.futures.archive_coverage import list_keys
from research.futures.spot_source_audit import SPOT_ROOT


def months_for(symbol: str) -> list[str]:
    prefix = f"{SPOT_ROOT}{symbol}/1d/"
    pattern = re.compile(re.escape(prefix) + re.escape(symbol) + r"-1d-(20\d\d-\d\d)\.zip$")
    months = [match.group(1) for key in list_keys(prefix)
              if (match := pattern.fullmatch(key)) and "2022" <= match.group(1)[:4] <= "2025"]
    if len(months) != len(set(months)):
        raise ValueError(f"duplicate spot archive month: {symbol}")
    return sorted(months)


def futures_months(database: Path) -> dict[str, set[str]]:
    result = defaultdict(set)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        for symbol, open_ms in db.execute("SELECT symbol, open_ms FROM prices WHERE tradable=1"):
            if not symbol.endswith("USDT"):
                continue
            month = datetime.fromtimestamp(open_ms / 1000, UTC).strftime("%Y-%m")
            if "2022" <= month[:4] <= "2025":
                result[symbol].add(month)
    return dict(result)


def inventory(spot_audit: dict, observed: dict[str, set[str]], workers: int) -> dict:
    source_names = set().union(*(set(x["same_name_overlap"])
                                 for x in spot_audit["by_year"].values()))
    candidates = sorted(source_names & observed.keys())
    spot_months = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(months_for, symbol): symbol for symbol in candidates}
        for future in as_completed(jobs):
            spot_months[jobs[future]] = future.result()
    by_year = {}
    for year in ("2022", "2023", "2024", "2025"):
        futures_pairs = {(symbol, month) for symbol, months in observed.items()
                         for month in months if month.startswith(year)}
        matched = {(symbol, month) for symbol, month in futures_pairs
                   if month in spot_months.get(symbol, ())}
        missing = sorted(futures_pairs - matched)
        by_year[year] = {
            "observed_tradable_futures_symbol_months": len(futures_pairs),
            "same_name_spot_zip_symbol_months": len(matched),
            "missing_spot_zip_symbol_months": len(missing),
            "missing_pairs": [[symbol, month] for symbol, month in missing],
        }
    return {"retrieved_at": datetime.now(UTC).isoformat(), "source": ENDPOINT,
            "meaning": "ZIP file presence only; no row-level, identity or PIT coverage claim",
            "candidate_symbols": len(candidates), "spot_months": dict(sorted(spot_months.items())),
            "by_year": by_year}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spot_audit", type=Path)
    parser.add_argument("futures_database", type=Path)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    print(json.dumps(inventory(json.loads(args.spot_audit.read_text()),
                               futures_months(args.futures_database), args.workers), indent=2))


if __name__ == "__main__":
    main()
