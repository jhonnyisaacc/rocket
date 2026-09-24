from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from research.futures.spot_eligibility import preflight


def test_basis_input_eligibility_uses_prior_days_only(tmp_path) -> None:
    futures = tmp_path / "futures.sqlite"
    spot = tmp_path / "spot.sqlite"
    start = int(datetime(2022, 1, 1, tzinfo=UTC).timestamp() * 1000)
    day = 86_400_000
    hour = 3_600_000
    with sqlite3.connect(futures) as db:
        db.execute("CREATE TABLE prices (symbol TEXT, open_ms INTEGER, quote_volume REAL, tradable INTEGER)")
        db.execute("CREATE TABLE funding (symbol TEXT, slot_ms INTEGER, stamp_ms INTEGER, "
                   "interval_hours INTEGER, rate REAL)")
        db.executemany("INSERT INTO prices VALUES (?,?,?,?)",
                       [("BTCUSDT", start + i * day, 6_000_000, 1) for i in range(30)])
        db.executemany("INSERT INTO funding VALUES (?,?,?,?,?)",
                       [("BTCUSDT", start + i * 8 * hour, start + i * 8 * hour, 8, 0.0)
                        for i in range(91)])
    with sqlite3.connect(spot) as db:
        db.execute("CREATE TABLE prices (symbol TEXT, open_ms INTEGER, quote_volume REAL, tradable INTEGER)")
        db.executemany("INSERT INTO prices VALUES (?,?,?,?)",
                       [("BTCUSDT", start + i * day, 6_000_000, 1) for i in range(30)])
    # The January 31 entry candle does not exist. Eligibility must not use it.
    report = preflight(futures, spot)
    assert report["eligible_symbols_by_entry_day"]["2022-01-31"] == ["BTCUSDT"]
    with sqlite3.connect(spot) as db:
        db.execute("UPDATE prices SET tradable=0 WHERE open_ms=?", (start + 15 * day,))
    report = preflight(futures, spot)
    assert report["by_year"]["2022"]["eligible_symbol_days"] == 0
