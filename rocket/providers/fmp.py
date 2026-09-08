"""Financial Modeling Prep. Optional process env FMP_API_KEY; never loads a dotenv file."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from rocket.config import env
from rocket.models import OperationalStatus
from rocket.providers.dispatch import failure_kind
from rocket.providers.http import get_read
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
            estimates[0].get("epsAvg")
            or estimates[0].get("estimatedEpsAvg")
            or estimates[0].get("estimatedEPSAvg")
            or estimates[0].get("estimatedEps")
        )
    eps_growth = None
    if current_eps not in (None, 0) and next_eps is not None:
        eps_growth = (next_eps - current_eps) / abs(current_eps)
    # Different fiscal-period estimates are not revisions of the same forecast.
    revision = None
    growth_basis = "forward EPS versus current EPS"
    growth = _record(payload.get("income_growth"))
    reported_growth = _finite(growth.get("growthEPS"))
    if eps_growth is None and reported_growth is not None:
        eps_growth = reported_growth
        growth_basis = "reported annual EPS growth"
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
        "eps_growth_basis": growth_basis if eps_growth is not None else None,
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
            response = get_read(client,
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
        payload = {}
        attempts = []
        for name, endpoint, params in (
            ("profile", "/profile", {"symbol": symbol}),
            ("ratios_ttm", "/ratios-ttm", {"symbol": symbol}),
            ("analyst_estimates", "/analyst-estimates", {"symbol": symbol, "period": "annual", "page": 0, "limit": 4}),
        ):
            try:
                payload[name] = self._get(endpoint, params=params)
                if any(row.get("symbol", symbol).upper() != symbol.upper() for row in _rows(payload[name])):
                    payload[name] = []
                    raise ValueError("provider symbol mismatch")
                attempts.append({"name": f"fmp:{name}", "status": "HEALTHY", "coverage": str(len(_rows(payload[name])))})
            except (httpx.HTTPError, TypeError, ValueError, RuntimeError) as exc:
                attempts.append({"name": f"fmp:{name}", "status": "UNAVAILABLE", "failure_kind": failure_kind(exc)})
        # Live current/forward EPS have incompatible windows unless explicitly aligned.
        # Use the provider's reported annual growth; estimates remain raw context only.
        payload["analyst_estimates"] = []
        if map_short_factors(payload)["company_fundamentals"] is None:
            try:
                growth = _rows(self._get("/income-statement-growth", params={"symbol": symbol, "period": "annual", "limit": 2}))
                eligible = []
                for row in growth:
                    try:
                        day = datetime.fromisoformat(str(row.get("date"))).replace(tzinfo=UTC)
                        if row.get("symbol", symbol).upper() == symbol.upper() and 0 <= (retrieved - day).days <= 550:
                            eligible.append(row)
                    except (ValueError, TypeError):
                        continue
                payload["income_growth"] = sorted(eligible, key=lambda row: row["date"], reverse=True)
                attempts.append({"name": "fmp:income_growth", "status": "HEALTHY", "coverage": str(len(eligible))})
            except (httpx.HTTPError, TypeError, ValueError, RuntimeError) as exc:
                attempts.append({"name": "fmp:income_growth", "status": "UNAVAILABLE", "failure_kind": failure_kind(exc)})
        factors = map_short_factors(payload)
        factors["provider_attempts"] = attempts
        factors["available_at"] = datetime.now(UTC).isoformat()
        factors["retrieved_at"] = factors["available_at"]
        factors["historical_available_at"] = None
        factors["availability_basis"] = "first observed current snapshot; not historical replay"
        factors["symbol"] = symbol.upper()
        factors["eps_kind"] = "REPORTED" if factors["eps_growth"] is not None else "UNKNOWN"
        factors["periods"] = payload.get("income_growth", [])
        observed = any(factors[key] is not None for key in ("company_fundamentals", "valuation_support", "earnings_revision_deterioration"))
        return ProviderResult(
            status=OperationalStatus.PARTIAL if any(a["status"] == "UNAVAILABLE" for a in attempts) else OperationalStatus.HEALTHY if observed else OperationalStatus.PARTIAL,
            records=(factors,),
            retrieved_at=datetime.fromisoformat(factors["retrieved_at"]),
            failure_kind=next((a["failure_kind"] for a in attempts if a.get("failure_kind") in {"Entitlement", "Authentication", "NotConfigured"}), None) if factors["company_fundamentals"] is None else None,
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

    def person_history(self, name="Nancy Pelosi") -> ProviderResult:
        from rocket.people import person_id
        from rocket.providers.dispatch import failure_kind
        if not self.api_key:
            return ProviderResult(OperationalStatus.UNAVAILABLE, source="fmp", failure_kind="NotConfigured")
        if person_id(name) != "nancy_pelosi":
            return ProviderResult(OperationalStatus.UNAVAILABLE, source="fmp",
                                  failure_kind="UnsupportedSourceFamily")
        try:
            rows = _rows(self._get("/house-trades-by-name", params={"name": "Pelosi"}))
            records = tuple(r for row in rows if person_id((r := parse_politician_row("house", row))["subject"]) == "nancy_pelosi")
            return ProviderResult(OperationalStatus.HEALTHY, records, datetime.now(UTC), source="fmp")
        except Exception as exc:
            return ProviderResult(OperationalStatus.UNAVAILABLE, source="fmp", failure_kind=failure_kind(exc))
