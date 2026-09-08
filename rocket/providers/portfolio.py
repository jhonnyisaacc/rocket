"""Deterministic listed-security context for caller-owned positions."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import httpx

from rocket.providers.quotes import acquire_quotes
from rocket.providers.shorts import _closes


def acquire_position_evidence(tickers: Sequence[str], *, now: datetime | None = None,
                              http: httpx.Client | None = None, include_news: bool = True) -> dict[str, Mapping]:
    owns = http is None
    client = http or httpx.Client(timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    output = {}
    try:
        quotes = acquire_quotes([{"ticker": ticker} for ticker in tickers], now=now, client=client)
        for ticker in dict.fromkeys(tickers):
            quote = quotes.get(ticker, {})
            row = {"provider_status": "UNAVAILABLE", "market_state": {}, "technical_condition": None,
                   "provider_attempts": [{"name": f"yahoo.quote:{ticker}",
                                          "status": "HEALTHY" if quote.get("status") == "OK" else "UNAVAILABLE",
                                          "failure_kind": quote.get("failure_kind") or quote.get("classification")} ]}
            output[ticker] = row
            if quote.get("status") != "OK":
                continue
            row["provider_status"] = "PARTIAL"
            row["market_state"] = {"current_price": quote["price"], "as_of": quote["observation_at"],
                                   "available_at": quote["available_at"], "source": quote["source"],
                                   "daily": False, "citation": quote.get("citation")}
            try:
                closes, observed = _closes(ticker, client)
                import math

                from rocket.clock import equity_observation_fresh
                if len(closes) < 21 or not all(math.isfinite(v) and v > 0 for v in closes[-21:]):
                    raise ValueError("insufficient finite history")
                if not equity_observation_fresh(observed, now or datetime.now(UTC), daily=False):
                    raise ValueError("stale history")
                row["technical_condition"] = "breakdown" if closes[-1] < min(closes[-21:-1]) else (
                    "weak" if closes[-1] < sum(closes[-20:]) / 20 else "healthy")
                row["technical_basis"] = {"source": "Yahoo Finance chart API", "observed_at": observed,
                                           "bars": len(closes), "rule": "20-session low / moving average",
                                           "average_20": sum(closes[-20:]) / 20,
                                           "low_20": min(closes[-21:-1]), "high_20": max(closes[-21:-1])}
                row["provider_status"] = "HEALTHY"
                row["provider_attempts"].append({"name": f"yahoo.history:{ticker}", "status": "HEALTHY",
                                                "coverage": str(len(closes))})
                row["market_state"]["available_at"] = (now or datetime.now(UTC)).isoformat()
            except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
                row["provider_attempts"].append({"name": f"yahoo.history:{ticker}", "status": "UNAVAILABLE",
                                                "failure_kind": type(exc).__name__})
            if http is None and include_news:
                from rocket.providers.news import company_news_context
                row.update(company_news_context(ticker))
    finally:
        if owns:
            client.close()
    return output
