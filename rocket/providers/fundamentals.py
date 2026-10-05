"""Shared fundamentals acquisition with field-level recovery and complete diagnostics."""

import math
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
    "eps_accounting",
    "eps_window",
    "eps_kind",
    "periods",
    "cik",
    "event_time",
    "citation",
)
VALUE_FIELDS = ("pe_ttm", "valuation_support", "earnings_revision_deterioration")
COMPARISON_PROVIDERS = ("fmp", "sec.edgar")
# Absolute growth gap, as a fraction. 0.25 is 25 percentage points.
EPS_DISAGREEMENT_GAP = 0.25
_ACCOUNTING = {"GAAP", "UNSPECIFIED", "FORWARD_ESTIMATE", "UNKNOWN"}
_WINDOWS = {"TTM", "QUARTER", "ANNUAL", "FORWARD", "UNKNOWN"}


@dataclass(frozen=True)
class FundamentalsAcquisition(Acquisition):
    row: Mapping[str, Any]


def _finite_growth(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def describe_eps(raw):
    """Accounting and window for one provider row.

    Explicit fields win. Otherwise the free-text basis is mapped. FMP annual
    growth is UNSPECIFIED: it is not a us-gaap tag.
    """
    accounting = raw.get("eps_accounting")
    window = raw.get("eps_window")
    if accounting not in _ACCOUNTING:
        accounting = None
    if window not in _WINDOWS:
        window = None
    if accounting is None or window is None:
        text = str(raw.get("eps_growth_basis") or "").lower()
        if "forward" in text:
            accounting = accounting or "FORWARD_ESTIMATE"
            window = window or "FORWARD"
        elif "ttm" in text:
            accounting = accounting or "GAAP"
            window = window or "TTM"
        elif "quarter" in text:
            accounting = accounting or "GAAP"
            window = window or "QUARTER"
        elif "annual" in text:
            accounting = accounting or "UNSPECIFIED"
            window = window or "ANNUAL"
        else:
            accounting = accounting or "UNKNOWN"
            window = window or "UNKNOWN"
    return accounting, window


def _basis_rank(view):
    if view["eps_accounting"] == "GAAP" and view["eps_window"] == "TTM":
        return 0
    if view["eps_accounting"] == "GAAP" and view["eps_window"] == "QUARTER":
        return 1
    return 2


def reconcile_eps(views):
    """Pick a comparable reported basis and record provider disagreement.

    ``views`` is in provider-chain order. GAAP TTM wins, then GAAP quarter,
    then the earlier provider. Opposite signs outrank a same-sign large gap.
    """
    if not views:
        return None, None
    selected = min(enumerate(views), key=lambda item: (_basis_rank(item[1]), item[0]))[1]
    if len(views) < 2:
        return selected, None
    opposite = False
    large = False
    for index, left in enumerate(views):
        for right in views[index + 1:]:
            if (left["eps_growth"] < 0) != (right["eps_growth"] < 0):
                opposite = True
            if abs(left["eps_growth"] - right["eps_growth"]) >= EPS_DISAGREEMENT_GAP:
                large = True
    reason = "opposite_sign" if opposite else "large_gap" if large else None
    return selected, {
        "flagged": reason is not None,
        "reason": reason,
        "threshold": EPS_DISAGREEMENT_GAP,
        "selected_provider": selected["provider"],
        "providers": [
            {
                "provider": view["provider"],
                "eps_growth": view["eps_growth"],
                "eps_accounting": view["eps_accounting"],
                "eps_window": view["eps_window"],
                "eps_growth_basis": view["eps_growth_basis"],
            }
            for view in views
        ],
    }


def _eps_sufficient(result):
    return bool(result.records) and result.records[0].get("company_fundamentals") is not None


def _has_eps(result):
    return result.status not in {OperationalStatus.ERROR, OperationalStatus.UNAVAILABLE} and _eps_sufficient(result)


def _chain(registry):
    config = registry.capability("fundamentals")
    return list(dict.fromkeys([config["primary"], *config.get("fallbacks", [])]))


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

    factories = {
        "fmp": lambda: capture("fmp", lambda: fmp.fundamentals(symbol)),
        "sec.edgar": lambda: capture("sec.edgar", lambda: edgar.fetch(symbol)),
        "massive": lambda: capture("massive", lambda: massive.fetch(symbol)),
    }

    def run(names, *, stop_early):
        if not names:
            return []
        if not stop_early:
            attempts = []
            for name in names:
                attempts.extend(run([name], stop_early=True))
            return attempts
        reg = Registry({"fundamentals": {"primary": names[0], "fallbacks": list(names[1:])}})
        for name in names:
            factory = factories.get(name)
            if factory is not None:
                reg.register("fundamentals", name, factory)
        acquired = reg.acquire("fundamentals", sufficient=_eps_sufficient)
        return list(acquired.attempts)

    names = _chain(registry)
    comparison = [name for name in names if name in COMPARISON_PROVIDERS]
    rest = [name for name in names if name not in COMPARISON_PROVIDERS]
    health = run(comparison, stop_early=False)
    if not any(_has_eps(result) for provider, result in observed if provider in COMPARISON_PROVIDERS):
        health.extend(run(rest, stop_early=True))

    last = {}
    for provider, result in observed:
        last[provider] = result
    views = []
    for name in names:
        result = last.get(name)
        if result is None or not _has_eps(result):
            continue
        raw = dict(result.records[0])
        accounting, window = describe_eps(raw)
        growth = _finite_growth(raw.get("eps_growth"))
        if growth is None:
            continue
        views.append({
            "provider": name,
            "eps_growth": growth,
            "eps_accounting": accounting,
            "eps_window": window,
            "eps_growth_basis": raw.get("eps_growth_basis"),
            "raw": raw,
            "result": result,
        })
    selected, disagreement = reconcile_eps(views)

    row = {
        "symbol": symbol.upper(),
        "company_fundamentals": None,
        "eps_growth": None,
        "pe_ttm": None,
        "valuation_support": None,
        "eps_kind": "UNKNOWN",
        "eps_accounting": "UNKNOWN",
        "eps_window": "UNKNOWN",
        "earnings_revision_deterioration": None,
        "eps_growth_basis": None,
        "eps_provider_disagreement": None,
        "historical_available_at": None,
    }
    provenance, endpoints = {}, []
    supplemental = ("eps_latest_quarter", "eps_ttm", "eps_quarter_yoy_growth",
                    "eps_ttm_yoy_growth", "revenue", "net_income", "shares_outstanding",
                    "shares_outstanding_unit", "shares_outstanding_date", "metrics", "metric_states")
    for provider, result in observed:
        raw = dict(result.records[0]) if result.records else {}
        endpoints.extend(dict(a) for a in raw.get(
            "provider_attempts", result.extras.get("provider_attempts", [])))
        if result.status in {OperationalStatus.ERROR, OperationalStatus.UNAVAILABLE}:
            continue
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
    if selected is not None:
        raw = selected["raw"]
        provider = selected["provider"]
        for key in EPS_FIELDS:
            row[key] = raw.get(key, row.get(key))
            if row[key] is not None:
                provenance[key] = provider
        row["eps_growth"] = selected["eps_growth"]
        row["eps_accounting"] = selected["eps_accounting"]
        row["eps_window"] = selected["eps_window"]
        row["company_fundamentals"] = selected["eps_growth"] < 0
        provenance["eps_growth"] = provider
        provenance["eps_accounting"] = provider
        provenance["eps_window"] = provider
        provenance["company_fundamentals"] = provider
    attempts = []
    for attempt in health:
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
        fundamentals_source=(selected["provider"] if selected else None) or next(iter(provenance.values()), None),
        field_provenance=provenance,
        provider_attempts=attempts + endpoints,
        eps_provider_disagreement=disagreement,
    )
    row = apply_price_valuation(row, price)
    # Preserve partial fields and endpoint diagnostics even when EPS acquisition exhausts.
    result = None
    if selected is not None:
        result = replace(selected["result"], records=(row,))
    return FundamentalsAcquisition(
        "fundamentals", result, tuple(health), True, row
    )


def fundamentals_row(symbol, **kwargs):
    return dict(acquire_fundamentals(symbol, **kwargs).row)
