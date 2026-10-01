"""Shared fundamentals acquisition with field-level recovery and complete diagnostics."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from rocket.models import OperationalStatus
from rocket.providers.dispatch import Acquisition
from rocket.providers.edgar import SECEDGAR, apply_price_valuation
from rocket.providers.fmp import FMPClient
from rocket.providers.massive import MassiveFundamentals
from rocket.providers.registry import Registry

EPS_FIELDS = (
    "company_fundamentals",
    "eps_growth",
    "eps_growth_basis",
    "eps_kind",
    "periods",
    "cik",
    "event_time",
    "citation",
)
VALUE_FIELDS = ("pe_ttm", "valuation_support", "earnings_revision_deterioration")


@dataclass(frozen=True)
class FundamentalsAcquisition(Acquisition):
    row: Mapping[str, Any]


def acquire_fundamentals(symbol, *, fmp=None, edgar=None, massive=None, registry=None,
                         state_dir=None, price=None):
    registry = registry or Registry()
    fmp = fmp or FMPClient()
    edgar = edgar or SECEDGAR(state_dir=state_dir)
    massive = massive or MassiveFundamentals()
    observed = []

    def capture(provider, fetch):
        result = fetch()
        observed.append((provider, result))
        return result

    registry.register(
        "fundamentals", "fmp", lambda: capture("fmp", lambda: fmp.fundamentals(symbol))
    )
    registry.register(
        "fundamentals", "sec.edgar", lambda: capture("sec.edgar", lambda: edgar.fetch(symbol))
    )
    registry.register(
        "fundamentals", "massive", lambda: capture("massive", lambda: massive.fetch(symbol))
    )
    acquired = registry.acquire(
        "fundamentals",
        sufficient=lambda r: (
            bool(r.records) and r.records[0].get("company_fundamentals") is not None
        ),
    )
    row = {
        "symbol": symbol.upper(),
        "company_fundamentals": None,
        "eps_growth": None,
        "pe_ttm": None,
        "valuation_support": None,
        "eps_kind": "UNKNOWN",
        "earnings_revision_deterioration": None,
        "eps_growth_basis": None,
        "historical_available_at": None,
    }
    provenance, endpoints = {}, []
    eps_provider = None
    supplemental = ("eps_latest_quarter", "eps_ttm", "eps_quarter_yoy_growth",
                    "eps_ttm_yoy_growth", "revenue", "net_income", "shares_outstanding",
                    "shares_outstanding_unit", "shares_outstanding_date", "metrics", "metric_states")
    for provider, result in observed:
        raw = dict(result.records[0]) if result.records else {}
        endpoints.extend(dict(a) for a in raw.get(
            "provider_attempts", result.extras.get("provider_attempts", [])))
        if result.status in {OperationalStatus.ERROR, OperationalStatus.UNAVAILABLE}:
            continue
        if eps_provider is None and raw.get("company_fundamentals") is not None:
            eps_provider = provider
            for key in EPS_FIELDS:
                row[key] = raw.get(key)
                if row[key] is not None:
                    provenance[key] = provider
        for key in (*VALUE_FIELDS, *supplemental):
            if row.get(key) is None and raw.get(key) is not None:
                row[key] = raw[key]
                provenance[key] = provider
        # Availability describes the current observed snapshots, not historical filings.
        for key in (
            "available_at",
            "retrieved_at",
            "availability_basis",
            "historical_available_at",
        ):
            if raw.get(key) is not None:
                row[key] = raw[key]
    attempts = []
    for attempt in acquired.attempts:
        provider = attempt.name
        attempts.append(
            {
                **attempt.to_dict(),
                "ticker": symbol.upper(),
                "provider": provider,
                "endpoint": "fundamentals",
            }
        )
    # A common diagnostic vocabulary; retain the older adapter detail additively.
    for attempt in attempts + endpoints:
        kind = attempt.get("failure_kind")
        if kind not in {None, "RateLimit", "Entitlement", "Empty", "NotFound", "HardError"}:
            attempt["original_failure_kind"] = kind
            attempt["failure_kind"] = "Empty" if kind in {"EmptyData", "InsufficientCoverage"} else "HardError"
    row.update(
        fundamentals_source=eps_provider or next(iter(provenance.values()), None),
        field_provenance=provenance,
        provider_attempts=attempts + endpoints,
    )
    row = apply_price_valuation(row, price)
    # Preserve partial fields and endpoint diagnostics even when EPS acquisition exhausts.
    result = acquired.result
    if result is not None:
        result = replace(result, records=(row,))
    return FundamentalsAcquisition(
        acquired.capability, result, acquired.attempts, acquired.required, row
    )


def fundamentals_row(symbol, **kwargs):
    return dict(acquire_fundamentals(symbol, **kwargs).row)
