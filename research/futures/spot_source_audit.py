"""Inventory Binance spot archive names against observed futures price names.

This is a source-feasibility audit, not a strategy or historical spot universe.
No price or return values are read. Run with the normalized futures database:
python -m research.futures.spot_source_audit FUTURES.sqlite > spot_source_audit.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from research.futures.archive_catalog import ENDPOINT, parse_page

SPOT_ROOT = "data/spot/monthly/klines/"


def list_spot_directories(*, timeout: float = 20.0) -> list[str]:
    names: set[str] = set()
    token: str | None = None
    seen: set[str] = set()
    while True:
        query = {"list-type": "2", "prefix": SPOT_ROOT, "delimiter": "/", "max-keys": "1000"}
        if token:
            query["continuation-token"] = token
        url = ENDPOINT + "?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, headers={"User-Agent": "rocket-spot-source-audit/1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            prefixes, next_token = parse_page(response.read())
        for prefix in prefixes:
            if not prefix.startswith(SPOT_ROOT) or not prefix.endswith("/"):
                raise ValueError(f"unexpected spot prefix: {prefix}")
            symbol = prefix[len(SPOT_ROOT) : -1]
            if not symbol or "/" in symbol:
                raise ValueError(f"unexpected spot directory: {prefix}")
            names.add(symbol)
        if next_token is None:
            return sorted(names)
        if next_token in seen:
            raise ValueError("repeated archive continuation token")
        seen.add(next_token)
        token = next_token


def observed_futures_names(database: Path) -> dict[str, set[str]]:
    years = defaultdict(set)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        for symbol, open_ms in db.execute("SELECT symbol, open_ms FROM prices WHERE tradable=1"):
            year = datetime.fromtimestamp(open_ms / 1000, UTC).year
            if year in (2022, 2023, 2024, 2025):
                years[str(year)].add(symbol)
    return dict(years)


def report(spot: list[str], futures: dict[str, set[str]]) -> dict:
    spot_set = set(spot)
    by_year = {}
    for year, names in sorted(futures.items()):
        usdt = {name for name in names if name.endswith("USDT")}
        overlap = sorted(usdt & spot_set)
        by_year[year] = {
            "observed_tradable_futures_usdt_names": len(usdt),
            "same_name_spot_archive_directories": len(overlap),
            "futures_without_same_name_spot_directory": sorted(usdt - spot_set),
            "same_name_overlap": overlap,
        }
    return {
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source": ENDPOINT,
        "spot_prefix": SPOT_ROOT,
        "meaning": "Directory names only; no monthly-file, row-level, PIT or basis coverage claim",
        "spot_directory_count": len(spot),
        "spot_usdt_directory_count": sum(name.endswith("USDT") for name in spot),
        "by_year": by_year,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("futures_database", type=Path)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    print(json.dumps(report(list_spot_directories(timeout=args.timeout),
                            observed_futures_names(args.futures_database)), indent=2))


if __name__ == "__main__":
    main()
