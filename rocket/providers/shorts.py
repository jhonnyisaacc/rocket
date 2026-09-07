"""Autonomous short snapshots from Yahoo history. Missing factors stay unknown."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from rocket.workflows.shorts import UNIVERSE


def _closes(symbol: str, http: httpx.Client) -> tuple[list[float], str | None]:
    response = http.get(
        f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={"range": "3mo", "interval": "1d"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]
    closes = [float(value) for value in result["indicators"]["quote"][0]["close"] if value is not None]
    stamp = datetime.fromtimestamp(result["meta"]["regularMarketTime"], UTC).isoformat()
    return closes, stamp


def acquire_short_snapshot(*, now: datetime | None = None, universe=None, http: httpx.Client | None = None) -> list[dict]:
    now = now or datetime.now(UTC)
    universe = universe or UNIVERSE
    symbols = sorted(set(universe) | set(universe.values()) | {"SPY"})
    owns = http is None
    client = http or httpx.Client(timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    histories: dict[str, tuple[list[float] | None, str, str | None, bool]] = {}
    try:
        for symbol in symbols:
            try:
                series, observed = _closes(symbol, client)
                stamp = datetime.fromisoformat(observed) if observed else None
                valid = (
                    stamp is not None
                    and stamp.tzinfo is not None
                    and timedelta(0) <= now - stamp <= timedelta(days=5)
                    and len(series) >= 21
                    and all(value > 0 for value in series[-21:])
                )
                histories[symbol] = (series, "Yahoo Finance chart API", observed, valid)
            except Exception:
                histories[symbol] = (None, "unavailable", None, False)
    finally:
        if owns:
            client.close()
    spy = histories["SPY"]
    rows = []
    for ticker, sector in universe.items():
        series, source, observed, valid = histories[ticker]
        sec = histories[sector]
        row = {
            "ticker": ticker,
            "source": source,
            "event_time": observed,
            "available_at": now.isoformat() if valid else None,
            "acquisition_mode": "LIVE",
            "required_factors": ["company_fundamentals", "technical_breakdown", "catalyst"],
            "provider_health": "HEALTHY" if valid else "DATA_UNAVAILABLE",
            "company_fundamentals": None,
            "catalyst": None,
            "earnings_revision_deterioration": None,
            "positioning_crowding": None,
            "valuation_support": None,
        }
        if valid and series:
            row["technical_breakdown"] = series[-1] < min(series[-21:-1])
        if spy[3] and spy[0]:
            bench = spy[0]
            row["macro_regime"] = "risk_off" if bench[-1] < sum(bench[-20:]) / 20 else "neutral"
        if sec[3] and spy[3] and sec[0] and spy[0]:
            sector_return = sec[0][-1] / sec[0][-21] - 1
            bench_return = spy[0][-1] / spy[0][-21] - 1
            row["sector_weakness"] = sector_return < 0 and sector_return < bench_return
        rows.append(row)
    return rows
