"""Autonomous short snapshots from Yahoo history. Missing factors stay unknown."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from rocket.workflows.shorts import UNIVERSE


def _closes(symbol: str, http: httpx.Client) -> tuple[list[float], str | None]:
    for host in ("query2", "query1"):
        try:
            response = http.get(
                f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"range": "3mo", "interval": "1d"},
                headers={"User-Agent": "Mozilla/5.0"}, timeout=15,
            )
            response.raise_for_status()
            data = response.json()["chart"]["result"][0]
            if not data.get("indicators", {}).get("quote"):
                raise ValueError("missing quote history")
            break
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            if host == "query1":
                raise
    result = response.json()["chart"]["result"][0]
    closes = [float(value) for value in result["indicators"]["quote"][0]["close"] if value is not None]
    stamp = datetime.fromtimestamp(result["meta"]["regularMarketTime"], UTC).isoformat()
    return closes, stamp


def acquire_short_snapshot(
    *,
    now: datetime | None = None,
    universe=None,
    http: httpx.Client | None = None,
    fundamentals: Callable[[str], Mapping[str, Any]] | None = None,
) -> list[dict]:
    fixed_now = now
    now = now or datetime.now(UTC)
    universe = UNIVERSE if universe is None else universe
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
                    and timedelta(0) <= (fixed_now or datetime.now(UTC)) - stamp <= timedelta(days=5)
                    and len(series) >= 21
                    and all(math.isfinite(value) and value > 0 for value in series[-21:])
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
            "required_factors": ["company_fundamentals", "technical_breakdown"],
            "provider_health": "HEALTHY" if valid else "DATA_UNAVAILABLE",
            "company_fundamentals": None,
            "catalyst": None,
            "earnings_revision_deterioration": None,
            "positioning_crowding": None,
            "valuation_support": None,
        }
        if valid and series:
            row["technical_breakdown"] = series[-1] < min(series[-21:-1])
        row["provider_attempts"] = [{"name": f"yahoo.history:{symbol}",
                                     "status": "HEALTHY" if histories[symbol][3] else "UNAVAILABLE",
                                     "coverage": str(len(histories[symbol][0] or []))}
                                    for symbol in dict.fromkeys((ticker, sector, "SPY"))]
        if fundamentals is not None:
            try:
                extra = fundamentals(ticker)
            except Exception as exc:
                extra = {"provider_attempts": [{"name": f"fundamentals:{ticker}", "status": "UNAVAILABLE",
                                                "failure_kind": type(exc).__name__}]}
            row["provider_attempts"].extend(extra.get("provider_attempts", []))
            if isinstance(extra, Mapping):
                for key in (
                    "company_fundamentals",
                    "earnings_revision_deterioration",
                    "valuation_support",
                    "pe_ttm",
                    "eps_growth",
                    "fundamentals_source",
                    "eps_growth_basis",
                ):
                    if key in extra:
                        row[key] = extra[key]
        if spy[3] and spy[0]:
            bench = spy[0]
            row["macro_regime"] = "risk_off" if bench[-1] < sum(bench[-20:]) / 20 else "neutral"
        if sec[3] and spy[3] and sec[0] and spy[0]:
            sector_return = sec[0][-1] / sec[0][-21] - 1
            bench_return = spy[0][-1] / spy[0][-21] - 1
            row["sector_weakness"] = sector_return < 0 and sector_return < bench_return
        if fundamentals is None:
            row["provider_attempts"].append({"name": f"fundamentals:{ticker}", "status": "UNAVAILABLE", "failure_kind": "NotConfigured"})
        row["provider_health"] = "HEALTHY" if all(p["status"] == "HEALTHY" for p in row["provider_attempts"]) else "PARTIAL" if valid else "UNAVAILABLE"
        rows.append(row)
    acquired = fixed_now or datetime.now(UTC)
    for row in rows:
        if row["available_at"] is not None:
            row["available_at"] = acquired.isoformat()
    return rows


def live_fundamentals_fetcher() -> Callable[[str], Mapping[str, Any]] | None:
    from rocket.providers.fmp import FMPClient

    client = FMPClient()
    if not client.configured():
        return None

    def _fetch(symbol: str) -> Mapping[str, Any]:
        result = client.fundamentals(symbol)
        if not result.records:
            return {}
        return result.records[0]

    return _fetch
