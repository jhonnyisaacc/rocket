"""Massive reported annual EPS; no estimates or historical availability imputation."""

import re
from datetime import UTC, datetime

import httpx

from rocket.config import env
from rocket.models import OperationalStatus
from rocket.providers.dispatch import failure_kind
from rocket.providers.fmp import _finite
from rocket.providers.http import get_read
from rocket.providers.protocols import ProviderResult

ENDPOINT = "https://api.massive.com/stocks/financials/v1/income-statements"


def normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    # Share classes retain their identity; do not guess a hyphen/dot conversion.
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", symbol):
        raise ValueError("unsupported ticker")
    return symbol


def reported_factors(rows, symbol, retrieved):
    valid = []
    for row in rows:
        if symbol not in row.get("tickers", []) or row.get("timeframe") != "annual":
            continue
        # Multiple share classes may have different per-share economics.
        if len(set(row["tickers"])) != 1 or not row.get("cik"):
            continue
        try:
            period = datetime.fromisoformat(row["period_end"]).replace(tzinfo=UTC)
            filing = datetime.fromisoformat(row["filing_date"]).replace(tzinfo=UTC)
            year = int(row["fiscal_year"])
        except (ValueError, KeyError, TypeError):
            continue
        eps = _finite(row.get("diluted_earnings_per_share"))
        if eps is None or not period <= filing <= retrieved:
            continue
        valid.append((period, filing, year, eps, row))
    valid.sort(key=lambda r: (r[0], r[1]), reverse=True)
    if not valid:
        raise ValueError("no identified reported annual EPS")
    latest = valid[0]
    prior = next((r for r in valid if r[2] == latest[2] - 1 and r[4]["cik"] == latest[4]["cik"]
                  and 330 <= (latest[0] - r[0]).days <= 400), None)
    if prior is None or prior[3] == 0 or (retrieved - latest[0]).days > 550:
        raise ValueError("no fresh comparable annual EPS pair")
    growth = (latest[3] - prior[3]) / abs(prior[3])
    if _finite(growth) is None:
        raise ValueError("nonfinite reported EPS growth")
    return {
        "symbol": symbol, "cik": latest[4]["cik"],
        "company_fundamentals": growth < 0, "eps_growth": growth,
        "eps_growth_basis": "reported annual diluted EPS growth; comparable consecutive fiscal years",
        "eps_kind": "REPORTED", "earnings_revision_deterioration": None,
        "valuation_support": None, "pe_ttm": None,
        "fundamentals_source": "massive", "citation": ENDPOINT,
        "event_time": latest[0].isoformat(), "available_at": retrieved.isoformat(),
        "retrieved_at": retrieved.isoformat(),
        "availability_basis": "first observed current provider snapshot; restatements possible; not historical replay",
        "historical_available_at": None,
        "periods": [{"period_end": r[0].date().isoformat(), "filing_date": r[1].date().isoformat(),
                     "fiscal_year": r[2], "diluted_eps": r[3]} for r in (latest, prior)],
    }


class MassiveFundamentals:
    def __init__(self, *, api_key=None, http=None):
        self.api_key = api_key if api_key is not None else env("MASSIVE_API_KEY")
        self.http = http

    def fetch(self, symbol: str, *, now=None) -> ProviderResult:
        if not self.api_key:
            return ProviderResult(OperationalStatus.UNAVAILABLE, source="massive", failure_kind="NotConfigured")
        owns = self.http is None
        client = self.http or httpx.Client(timeout=20)
        try:
            symbol = normalize_symbol(symbol)
            response = get_read(client, ENDPOINT, params={"tickers": symbol, "timeframe": "annual",
                                                         "limit": 6, "sort": "period_end.desc"},
                                headers={"Authorization": f"Bearer {self.api_key}"})
            raw = response.json()
            if raw.get("status") != "OK" or not isinstance(raw.get("results"), list):
                raise ValueError("invalid income statement response")
            retrieved = now or datetime.now(UTC)
            row = reported_factors(raw["results"], symbol, retrieved)
            return ProviderResult(OperationalStatus.HEALTHY, (row,), retrieved, source="massive",
                                  extras={"request_id": raw.get("request_id"), "endpoint": ENDPOINT})
        except Exception as exc:
            return ProviderResult(OperationalStatus.UNAVAILABLE, retrieved_at=now or datetime.now(UTC),
                                  source="massive", failure_kind=failure_kind(exc))
        finally:
            if owns:
                client.close()
