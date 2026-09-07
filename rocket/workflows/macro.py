"""Canonical US rates and liquidity. Cava is never required."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from rocket.models import (
    Evidence,
    EvidenceKind,
    Mode,
    OperationalReport,
    OperationalStatus,
    Provenance,
    ProviderHealth,
    ResearchResult,
    ResearchStatus,
)
from rocket.pit import iso, parse_datetime
from rocket.providers.fred import FredMacroSeries, _record_date, _record_value
from rocket.store import ResearchStore

FACTORS = {"EFFR": 5, "WDTGAL": 10, "RRPONTSYD": 5, "WALCL": 10}
WORKFLOW = "macro"


def _stamp(raw: Any, *, now: datetime) -> datetime | None:
    text = _record_date({"date": raw}) if not isinstance(raw, str) else raw
    if not text:
        return None
    try:
        if "T" in text:
            parsed = parse_datetime(text)
        else:
            parsed = datetime.fromisoformat(text[:10]).replace(tzinfo=UTC)
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC) if parsed <= now else None
    except (TypeError, ValueError):
        return None


def macro_is_usable(context: Mapping[str, Any] | None, now: datetime) -> bool:
    if not context or context.get("contract") != "current_macro_v1" or context.get("status") != "OK":
        return False
    try:
        retrieved = parse_datetime(context["retrieved_at"])
        expires = parse_datetime(context["expires_at"])
        if retrieved is None or expires is None or not retrieved <= now < expires:
            return False
        for symbol, days in FACTORS.items():
            row = context["factors"][symbol]
            stamp = parse_datetime(row["observation_at"])
            if (
                row["status"] != "OK"
                or stamp is None
                or not isinstance(row.get("value"), (int, float))
                or isinstance(row.get("value"), bool)
                or not timedelta(0) <= now - stamp <= timedelta(days=days)
            ):
                return False
        return True
    except (KeyError, ValueError, TypeError):
        return False


class MacroWorkflow:
    name = WORKFLOW

    def __init__(self, *, store: ResearchStore | None = None, fetcher: Callable | None = None):
        self.store = store
        self.series = FredMacroSeries(fetcher=fetcher)

    def run(self, *, now: datetime | None = None) -> ResearchResult:
        started = now or datetime.now(UTC)
        factors: dict[str, Any] = {}
        warnings: list[str] = []
        providers: list[ProviderHealth] = []
        evidence: list[Evidence] = []
        for symbol, days in FACTORS.items():
            result = self.series.fetch(symbol, now=started)
            providers.append(
                ProviderHealth(
                    name=f"fred:{symbol}",
                    status=result.status,
                    retrieved_at=result.retrieved_at,
                    failure_kind=result.failure_kind,
                )
            )
            if result.status is not OperationalStatus.HEALTHY:
                factors[symbol] = {"status": "UNAVAILABLE", "failure_kind": result.failure_kind}
                warnings.append(f"{symbol}: provider unavailable")
                continue
            values: dict[datetime, float] = {}
            for row in result.records:
                stamp = _stamp(_record_date(row), now=started)
                value = _record_value(row, symbol)
                if stamp is None or value is None:
                    continue
                values[stamp] = value
            if not values:
                factors[symbol] = {"status": "UNAVAILABLE", "failure_kind": "EmptySeries"}
                warnings.append(f"{symbol}: provider unavailable")
                continue
            dates = sorted(values)
            stamp = dates[-1]
            prior_dates = [item for item in dates if item <= stamp - timedelta(days=28)]
            if not prior_dates:
                factors[symbol] = {
                    "status": "INSUFFICIENT",
                    "failure_kind": "NO_4W_HISTORY",
                    "observation_at": iso(stamp),
                    "value": values[stamp],
                    "source": result.source,
                    "citation": f"https://fred.stlouisfed.org/series/{symbol}",
                }
                warnings.append(f"{symbol}: no observation at least 28 days before the latest print")
                continue
            prior = prior_dates[-1]
            fresh = started - stamp <= timedelta(days=days)
            retrieved = result.retrieved_at or started
            factors[symbol] = {
                "value": values[stamp],
                "observation_at": iso(stamp),
                "retrieved_at": iso(retrieved),
                "available_at": iso(retrieved),
                "availability_basis": "first observed by current retrieval; not a historical release claim",
                "source": result.source,
                "citation": f"https://fred.stlouisfed.org/series/{symbol}",
                "prior_observation_at": iso(prior),
                "prior_value": values[prior],
                "change_4w": values[stamp] - values[prior],
                "status": "OK" if fresh else "STALE",
                "max_observation_age_days": days,
            }
            if not fresh:
                warnings.append(f"{symbol}: stale observation")
            else:
                evidence.append(
                    Evidence(
                        source=result.source or "fred",
                        reference=symbol,
                        claim=f"{symbol} latest observation is {values[stamp]}",
                        kind=EvidenceKind.FACT,
                        event_time=stamp,
                        observed_at=stamp,
                        available_at=retrieved,
                        retrieved_at=retrieved,
                        decision_time=started,
                        provenance=Provenance.PROVIDER_RESULT,
                    )
                )
        ok = all(row.get("status") == "OK" for row in factors.values()) and len(factors) == len(FACTORS)
        rates = factors.get("EFFR", {}).get("change_4w")
        regime = (
            ("neutral" if rates == 0 else "bullish" if rates is not None and rates < 0 else "bearish")
            if ok
            else "unknown"
        )
        payload: dict[str, Any] = {
            "contract": "current_macro_v1",
            "status": "OK" if ok else "UNAVAILABLE",
            "regime": regime,
            "regime_basis": (
                "4-week effective Fed funds direction: falling/supportive, rising/restrictive, unchanged/neutral"
            ),
            "factors": factors,
            "warnings": warnings,
            "retrieved_at": iso(started),
            "available_at": iso(started),
            "expires_at": iso(started + timedelta(hours=6)),
            "scope": "US rates and monetary liquidity; no Cava validation implied",
            "execution_enabled": False,
        }
        if ok:
            payload["net_liquidity_million_usd"] = (
                factors["WALCL"]["value"] - factors["WDTGAL"]["value"] - factors["RRPONTSYD"]["value"] * 1000
            )
        failed = sum(item.status is OperationalStatus.UNAVAILABLE for item in providers)
        if failed == len(providers):
            operational = OperationalStatus.UNAVAILABLE
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
        elif not ok:
            operational = OperationalStatus.PARTIAL
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
        else:
            operational = OperationalStatus.HEALTHY
            research = ResearchStatus.NO_SETUP
        result = ResearchResult(
            workflow=WORKFLOW,
            status=research,
            operational=OperationalReport(status=operational, providers=tuple(providers)),
            decision_time=started,
            started_at=started,
            completed_at=started,
            mode=Mode.LIVE,
            payload=payload,
            evidence=tuple(evidence),
            warnings=tuple(warnings),
        )
        if self.store:
            self.store.save_result(result)
            self.store.save_context("macro", payload)
        return result
