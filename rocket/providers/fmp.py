"""Financial Modeling Prep. Optional process env FMP_API_KEY; never loads a dotenv file."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from rocket.config import env
from rocket.models import OperationalStatus
from rocket.providers.protocols import ProviderResult

FMP_STABLE_URL = "https://financialmodelingprep.com/stable"


def _finite(value: Any) -> float | None:
    try:
        if value in (None, "") or isinstance(value, bool):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _record(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list) and payload and isinstance(payload[0], Mapping):
        return dict(payload[0])
    if isinstance(payload, Mapping) and "Error Message" not in payload and "Error" not in payload:
        return dict(payload)
    return {}


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, Mapping)]
    return []


def map_short_factors(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Map FMP profile/ratios/estimates onto shorts factors. Missing stays None."""
    profile = _record(payload.get("profile"))
    ratios = _record(payload.get("ratios_ttm"))
    estimates = _rows(payload.get("analyst_estimates"))
    pe = _finite(ratios.get("peRatioTTM") or ratios.get("priceToEarningsRatioTTM") or profile.get("pe"))
    current_eps = _finite(profile.get("eps") or profile.get("epsTTM") or ratios.get("netIncomePerShareTTM"))
    next_eps = None
    if estimates:
        next_eps = _finite(
            estimates[0].get("estimatedEpsAvg")
            or estimates[0].get("estimatedEPSAvg")
            or estimates[0].get("estimatedEps")
        )
    eps_growth = None
    if current_eps not in (None, 0) and next_eps is not None:
        eps_growth = (next_eps - current_eps) / abs(current_eps)
    prior_eps = None
    if len(estimates) >= 2:
        prior_eps = _finite(
            estimates[1].get("estimatedEpsAvg")
            or estimates[1].get("estimatedEPSAvg")
            or estimates[1].get("estimatedEps")
        )
    revision = None
    if next_eps is not None and prior_eps is not None:
        revision = next_eps < prior_eps
    valuation_support = None
    if pe is not None and pe > 0:
        valuation_support = pe <= 15
    company_fundamentals = None
    if eps_growth is not None:
        company_fundamentals = eps_growth < 0
    return {
        "company_fundamentals": company_fundamentals,
        "earnings_revision_deterioration": revision,
        "valuation_support": valuation_support,
        "pe_ttm": pe,
        "eps_growth": eps_growth,
        "fundamentals_source": "fmp",
    }


def parse_politician_row(chamber: str, row: Mapping[str, Any]) -> dict[str, Any]:
    first = str(row.get("firstName") or "").strip()
    last = str(row.get("lastName") or "").strip()
    name = (f"{first} {last}".strip() or str(row.get("office") or "").strip() or "UNKNOWN")
    link = str(row.get("link") or "").strip()
    if not link:
        link = (
            f"missing-link::{chamber}::{row.get('disclosureDate', '')}::"
            f"{row.get('symbol', '')}::{name}::{row.get('transactionDate', '')}"
        )
    return {
        "subject": name,
        "asset": str(row.get("symbol") or "").strip() or "UNKNOWN",
        "transaction_type": str(row.get("type") or row.get("transactionType") or "UNKNOWN").strip(),
        "transaction_date": str(row.get("transactionDate") or "").strip() or None,
        "disclosure_date": str(row.get("disclosureDate") or "").strip() or None,
        "owner": str(row.get("owner") or "").strip() or None,
        "source_url": link,
        "provider": "fmp",
        "chamber": chamber,
        "record_semantics": "SECONDARY_TRANSACTION_ROW",
    }


class FMPClient:
    def __init__(self, *, api_key: str | None = None, http: httpx.Client | None = None):
        self.api_key = api_key if api_key is not None else env("FMP_API_KEY")
        self.http = http

    def configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        if not self.api_key:
            raise RuntimeError("FMP_API_KEY is not set")
        owns = self.http is None
        client = self.http or httpx.Client(timeout=20.0, headers={"User-Agent": "rocket-research"})
        try:
            response = client.get(
                f"{FMP_STABLE_URL}{path}",
                params={"apikey": self.api_key, **(params or {})},
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns:
                client.close()
        if isinstance(payload, Mapping) and (payload.get("Error Message") or payload.get("Error")):
            raise RuntimeError(str(payload.get("Error Message") or payload.get("Error")))
        return payload

    def fundamentals(self, symbol: str) -> ProviderResult:
        retrieved = datetime.now(UTC)
        if not self.api_key:
            return ProviderResult(
                status=OperationalStatus.UNAVAILABLE,
                failure_kind="NO_SETUP",
                source="fmp",
                extras={"symbol": symbol, "reason": "FMP_API_KEY unset"},
            )
        try:
            payload = {
                "profile": self._get("/profile", params={"symbol": symbol}),
                "ratios_ttm": self._get("/ratios-ttm", params={"symbol": symbol}),
                "analyst_estimates": self._get(
                    "/analyst-estimates",
                    params={"symbol": symbol, "period": "annual", "page": 0, "limit": 4},
                ),
            }
        except (httpx.HTTPError, TypeError, ValueError, RuntimeError) as exc:
            return ProviderResult(
                status=OperationalStatus.UNAVAILABLE,
                failure_kind=type(exc).__name__,
                source="fmp",
                extras={"symbol": symbol},
            )
        factors = map_short_factors(payload)
        observed = any(factors[key] is not None for key in ("company_fundamentals", "valuation_support", "earnings_revision_deterioration"))
        return ProviderResult(
            status=OperationalStatus.HEALTHY if observed else OperationalStatus.PARTIAL,
            records=(factors,),
            retrieved_at=retrieved,
            source="fmp",
            extras={"symbol": symbol.upper()},
        )

    def politician_trades(self) -> ProviderResult:
        retrieved = datetime.now(UTC)
        if not self.api_key:
            return ProviderResult(
                status=OperationalStatus.UNAVAILABLE,
                failure_kind="NO_SETUP",
                source="fmp",
                extras={"reason": "FMP_API_KEY unset"},
            )
        try:
            house = _rows(self._get("/house-latest"))
            senate = _rows(self._get("/senate-latest"))
        except (httpx.HTTPError, TypeError, ValueError, RuntimeError) as exc:
            return ProviderResult(
                status=OperationalStatus.UNAVAILABLE,
                failure_kind=type(exc).__name__,
                source="fmp",
            )
        records = tuple(
            parse_politician_row("house", row) for row in house
        ) + tuple(parse_politician_row("senate", row) for row in senate)
        return ProviderResult(
            status=OperationalStatus.HEALTHY if records else OperationalStatus.PARTIAL,
            records=records,
            retrieved_at=retrieved,
            source="fmp",
        )
