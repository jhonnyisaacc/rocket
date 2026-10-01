"""Loaders for the crypto research datasets. Read-only; no keys, no orders.

Reuse: market_check.metrics (performance, deflated_sharpe) and
market_check.bs (Black-Scholes put pricer) instead of reimplementing them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from rocket.config import PACKAGE_ROOT

DATA = PACKAGE_ROOT / "data" / "crypto"


@dataclass(frozen=True)
class Bar:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float


def _read(name: str) -> dict:
    return json.loads((DATA / name).read_text())


def load_btc_daily() -> list[Bar]:
    payload = _read("btc_daily.json")
    bars = []
    for row in payload["rows"]:
        day = datetime.fromtimestamp(row["t"] / 1000, tz=timezone.utc).date()
        bars.append(
            Bar(day, row["o"], row["h"], row["l"], row["c"], row["v"])
        )
    return sorted(bars, key=lambda b: b.day)


def load_funding_daily() -> dict[date, dict[str, float]]:
    """Median-able daily funding per venue, as fractions per day.

    Binance/Bybit fund every 8h; the daily figure compounds the day's prints.
    """
    out: dict[date, dict[str, float]] = {}
    specs = (("funding_binance.json", "binance"), ("funding_bybit.json", "bybit"))
    for filename, venue in specs:
        try:
            payload = _read(filename)
        except FileNotFoundError:
            continue
        by_day: dict[date, list[float]] = {}
        for row in payload["rows"]:
            if venue == "binance":
                ts, rate = int(row["fundingTime"]), float(row["fundingRate"])
            else:
                ts, rate = int(row["fundingRateTimestamp"]), float(row["fundingRate"])
            day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
            by_day.setdefault(day, []).append(rate)
        for day, rates in by_day.items():
            gross = 1.0
            for rate in rates:
                gross *= 1 + rate
            out.setdefault(day, {})[venue] = gross - 1
    return out


def load_dvol() -> dict[date, float]:
    """Deribit DVOL daily closes ([t, o, h, l, c]). Gaps stay gaps."""
    payload = _read("dvol.json")
    out: dict[date, float] = {}
    for row in payload["rows"]:
        ts, _o, _h, _l, close = row
        if not ts or close is None:
            continue
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
        out[day] = float(close)
    return out


def load_events() -> dict[str, list[date]]:
    """FOMC decision dates (2021+, from the Fed calendar page) and US
    general elections. CPI/payrolls were not sourced from a free,
    machine-readable calendar; pre-event tests use FOMC plus elections."""
    payload = json.loads((DATA / "events.json").read_text())
    out: dict[str, list[date]] = {}
    for key in ("fomc", "elections"):
        out[key] = [
            date.fromisoformat(item) for item in payload.get(key, [])
        ]
    return out


# Analytical crash windows (peak-to-trough-plus-rebound), used for the
# per-crash tables. Windows are fixed before any rule is evaluated.
CRASHES: tuple[tuple[str, str, str], ...] = (
    ("2020-03 covid", "2020-02-20", "2020-04-30"),
    ("2021-05 deleverage", "2021-04-15", "2021-07-31"),
    ("2022-05/06 luna", "2022-04-01", "2022-07-31"),
    ("2022-11 ftx", "2022-10-01", "2022-12-31"),
    ("2024-08 yen", "2024-07-15", "2024-09-30"),
    ("2025-04 tariffs", "2025-02-15", "2025-06-30"),
    ("2026 decline", "2025-10-01", "2026-09-30"),
)
