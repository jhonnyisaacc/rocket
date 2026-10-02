"""Measure causal spot/perpetual daily-row overlap without reading price values.

The prior completed day supplies a potential basis observation. Entry and next
perpetual opens are checked only for outcome coverage; missing exits still need
explicit cessation handling in a later frozen experiment.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

DAY_MS = 86_400_000


def audit(futures_db: Path, spot_db: Path) -> dict:
    counts: dict[str, Counter] = defaultdict(Counter)
    missing_prior_spot: dict[str, Counter] = defaultdict(Counter)
    missing_exit: dict[str, Counter] = defaultdict(Counter)
    with sqlite3.connect(f"file:{futures_db}?mode=ro", uri=True) as db:
        db.execute("ATTACH DATABASE ? AS spot", (f"file:{spot_db}?mode=ro",))
        query = """
          SELECT f.symbol, f.open_ms, f.tradable, p.tradable, s.tradable,
                 e.tradable
          FROM prices AS f
          LEFT JOIN prices AS p ON p.symbol=f.symbol AND p.open_ms=f.open_ms-?
          LEFT JOIN spot.prices AS s ON s.symbol=f.symbol AND s.open_ms=f.open_ms-?
          LEFT JOIN prices AS e ON e.symbol=f.symbol AND e.open_ms=f.open_ms+?
          WHERE f.symbol LIKE '%USDT'
            AND f.open_ms>=? AND f.open_ms<?
          ORDER BY f.open_ms, f.symbol
        """
        start = int(datetime(2022, 1, 1, tzinfo=UTC).timestamp() * 1000)
        end = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp() * 1000)
        for symbol, stamp, entry, prior_future, prior_spot, exit_ in db.execute(
                query, (DAY_MS, DAY_MS, DAY_MS, start, end)):
            year = str(datetime.fromtimestamp(stamp / 1000, UTC).year)
            row = counts[year]
            row["observed_future_days"] += 1
            if not entry:
                row["nontradable_entry_future_days"] += 1
                continue
            row["tradable_entry_future_days"] += 1
            if not prior_future:
                row["missing_or_nontradable_prior_future"] += 1
                continue
            row["prior_future_ready_days"] += 1
            if not prior_spot:
                row["missing_or_nontradable_prior_spot"] += 1
                missing_prior_spot[year][symbol] += 1
                continue
            row["prior_spot_and_future_ready_days"] += 1
            if not exit_:
                row["missing_or_nontradable_next_future_open"] += 1
                missing_exit[year][symbol] += 1
                continue
            row["next_future_open_ready_days"] += 1
    return {
        "audited_at": datetime.now(UTC).isoformat(),
        "meaning": "daily-row availability only; no basis values, returns, PIT universe or strategy outcome",
        "by_year": {year: dict(counts[year]) for year in sorted(counts)},
        "missing_prior_spot_by_symbol": {
            year: dict(missing_prior_spot[year].most_common()) for year in sorted(counts)},
        "missing_next_future_open_by_symbol": {
            year: dict(missing_exit[year].most_common()) for year in sorted(counts)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("futures_database", type=Path)
    parser.add_argument("spot_database", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.futures_database, args.spot_database), indent=2))


if __name__ == "__main__":
    main()
