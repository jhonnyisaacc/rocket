"""Yahoo chart quotes for listed equity/ETF symbols."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import httpx

from rocket.clock import equity_observation_fresh
from rocket.models import OperationalStatus
from rocket.providers.protocols import ProviderResult


def acquire_quotes(
    watches: Sequence[Mapping],
    *,
    now: datetime | None = None,
    client: httpx.Client | None = None,
) -> dict[str, dict]:
    current = now or datetime.now(UTC)
    output: dict[str, dict] = {}
    owns = client is None
    http = client or httpx.Client(timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    try:
        for watch in watches:
            ticker = str(watch.get("ticker") or "").strip().upper()
            symbol = str(watch.get("price_symbol") or ticker).strip().upper()
            row = {
                "ticker": ticker,
                "symbol": symbol,
                "price_basis": watch.get("price_basis", "listed security"),
                "source": "Yahoo Finance chart API",
                "source_reference": watch.get("source_reference"),
                "retrieved_at": current.isoformat(),
                "classification": "DATA_TEMPORARILY_UNAVAILABLE",
            }
            for host in ("query2", "query1"):
                try:
                    url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}"
                    response = http.get(url, params={"range": "5d", "interval": "1d"})
                    response.raise_for_status()
                    data = response.json()["chart"]["result"][0]
                    meta = data["meta"]
                    row["identity"] = {
                        key: meta.get(key)
                        for key in (
                            "symbol",
                            "longName",
                            "shortName",
                            "exchangeName",
                            "instrumentType",
                            "currency",
                        )
                    }
                    if meta.get("symbol", "").upper() != symbol.upper() or meta.get("instrumentType") not in {
                        "EQUITY",
                        "ETF",
                    }:
                        row["classification"] = "NON_STANDARD_ASSET"
                        break
                    expected = watch.get("expected_provider_name")
                    if expected and expected != meta.get("longName"):
                        row["classification"] = "PROVIDER_MAPPING_REQUIRED"
                        break
                    expected_exchange = watch.get("expected_exchange")
                    if expected_exchange and expected_exchange != meta.get("exchangeName"):
                        row["classification"] = "PROVIDER_MAPPING_REQUIRED"
                        break
                    current = now or datetime.now(UTC)
                    stamp = datetime.fromtimestamp(meta["regularMarketTime"], UTC)
                    price = float(meta["regularMarketPrice"])
                    row.update(
                        price=price,
                        observation_at=stamp.isoformat(),
                        available_at=current.isoformat(),
                        citation=url,
                        classification="PROVIDER_SUPPORTED",
                        status="OK"
                        if price > 0 and equity_observation_fresh(stamp.isoformat(), current, daily=False)
                        else "STALE",
                        freshness_basis="latest regular-session quote; 20-minute ceiling during open market",
                    )
                    break
                except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                    row["failure_kind"] = type(exc).__name__
            row.setdefault("status", "UNAVAILABLE")
            if ticker:
                output[ticker] = row
    finally:
        if owns:
            http.close()
    return output


class YahooQuotes:
    def __init__(self, *, client: httpx.Client | None = None):
        self.client = client

    def fetch(self, symbols: tuple[str, ...], *, now: datetime | None = None) -> ProviderResult:
        watches = [{"ticker": symbol} for symbol in symbols]
        rows = acquire_quotes(watches, now=now, client=self.client)
        records = tuple(rows.values())
        healthy = sum(1 for row in records if row.get("status") == "OK")
        if healthy == len(records) and records:
            status = OperationalStatus.HEALTHY
        elif healthy:
            status = OperationalStatus.PARTIAL
        else:
            status = OperationalStatus.UNAVAILABLE
        return ProviderResult(
            status=status,
            records=records,
            retrieved_at=now or datetime.now(UTC),
            source="yahoo",
        )
