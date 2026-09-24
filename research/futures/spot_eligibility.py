"""Return-free, point-in-time input eligibility for a possible basis factor.

Uses only the 30 completed days before each entry: exact same-name spot and
perpetual bars, lagged quote turnover, and historical funding cadence. This
does not rank the basis, inspect entry/exit prices, or form a strategy.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from research.futures.fut001 import funding_window
from research.futures.normalize_archives import DAY_MS

MIN_QUOTE_VOLUME = 5_000_000.0
LOOKBACK_DAYS = 30
START_MS = int(datetime(2022, 1, 1, tzinfo=UTC).timestamp() * 1000)
END_MS = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp() * 1000)


def preflight(futures_db: Path, spot_db: Path) -> dict:
    by_day: dict[str, list[str]] = defaultdict(list)
    failures: Counter = Counter()
    with sqlite3.connect(f"file:{futures_db}?mode=ro", uri=True) as db:
        db.execute("ATTACH DATABASE ? AS spot", (f"file:{spot_db}?mode=ro",))
        symbols = [row[0] for row in db.execute(
            "SELECT DISTINCT f.symbol FROM prices AS f JOIN spot.prices AS s "
            "ON s.symbol=f.symbol WHERE f.symbol LIKE '%USDT' ORDER BY f.symbol")]
        for symbol in symbols:
            future = {row[0]: row for row in db.execute(
                "SELECT open_ms,quote_volume,tradable FROM prices WHERE symbol=? ORDER BY open_ms",
                (symbol,))}
            spot = {row[0]: row for row in db.execute(
                "SELECT open_ms,quote_volume,tradable FROM spot.prices WHERE symbol=? ORDER BY open_ms",
                (symbol,))}
            funding = list(db.execute(
                "SELECT slot_ms,stamp_ms,interval_hours,rate FROM funding "
                "WHERE symbol=? ORDER BY slot_ms", (symbol,)))
            slots = [row[0] for row in funding]
            for prior in sorted(future):
                entry = prior + DAY_MS
                if not START_MS <= entry < END_MS:
                    continue
                if datetime.fromtimestamp(entry / 1000, UTC).year != \
                        datetime.fromtimestamp((entry + DAY_MS) / 1000, UTC).year:
                    continue
                failures["candidate_prior_future_days"] += 1
                stamps = [prior - offset * DAY_MS for offset in range(LOOKBACK_DAYS)]
                f_rows = [future.get(stamp) for stamp in stamps]
                if any(row is None or not row[2] for row in f_rows):
                    failures["invalid_prior_future_history"] += 1
                    continue
                s_rows = [spot.get(stamp) for stamp in stamps]
                if any(row is None or not row[2] for row in s_rows):
                    failures["invalid_prior_spot_history"] += 1
                    continue
                if sum(row[1] for row in f_rows) / LOOKBACK_DAYS < MIN_QUOTE_VOLUME:
                    failures["low_prior_future_turnover"] += 1
                    continue
                if sum(row[1] for row in s_rows) / LOOKBACK_DAYS < MIN_QUOTE_VOLUME:
                    failures["low_prior_spot_turnover"] += 1
                    continue
                funding_ok, _ = funding_window(funding, slots,
                                               prior - (LOOKBACK_DAYS - 1) * DAY_MS, entry)
                if not funding_ok:
                    failures["incomplete_prior_funding"] += 1
                    continue
                day = datetime.fromtimestamp(entry / 1000, UTC).date().isoformat()
                by_day[day].append(symbol)
    by_year = {}
    for year in range(2022, 2026):
        days = {day: names for day, names in by_day.items() if day.startswith(str(year))}
        by_year[str(year)] = {
            "eligible_symbol_days": sum(map(len, days.values())),
            "eligible_symbols": len(set().union(*(set(names) for names in days.values()))),
            "days_with_at_least_20_names": sum(len(names) >= 20 for names in days.values()),
            "days_with_any_name": len(days),
            "min_daily_names": min(map(len, days.values()), default=0),
            "median_daily_names": sorted(map(len, days.values()))[len(days) // 2] if days else 0,
            "max_daily_names": max(map(len, days.values()), default=0),
        }
    return {"audited_at": datetime.now(UTC).isoformat(),
            "meaning": "return-free causal input eligibility, not a strategy or entry-fill claim",
            "rule": {"lookback_days": LOOKBACK_DAYS,
                     "mean_prior_quote_turnover_floor_usdt_each_market": MIN_QUOTE_VOLUME,
                     "funding": "complete prior 30-day venue cadence"},
            "failure_counts": dict(failures), "by_year": by_year,
            "eligible_symbols_by_entry_day": dict(sorted(by_day.items()))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("futures_database", type=Path)
    parser.add_argument("spot_database", type=Path)
    args = parser.parse_args()
    print(json.dumps(preflight(args.futures_database, args.spot_database), indent=2))


if __name__ == "__main__":
    main()
