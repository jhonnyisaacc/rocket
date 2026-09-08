"""Canonical US rates and liquidity. Cava is never required."""

from __future__ import annotations

import math
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
    ReasonCode,
    ResearchReason,
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
                or not math.isfinite(row["value"])
                or stamp > now
                or not 0 <= (now.date() - stamp.date()).days <= days
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
        acquired = {symbol: self.series.fetch(symbol, now=now) for symbol in FACTORS}
        decided = now or datetime.now(UTC)
        for symbol, days in FACTORS.items():
            result = acquired[symbol]
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
                stamp = _stamp(_record_date(row), now=decided)
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
            fresh = 0 <= (decided.date() - stamp.date()).days <= days and (result.retrieved_at is not None and result.retrieved_at <= decided)
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
                "freshness_basis": "inclusive calendar dates for date-only source observations",
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
                        decision_time=decided,
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
            "retrieved_at": iso(decided),
            "available_at": iso(decided),
            "expires_at": iso(decided + timedelta(hours=6)),
            "scope": "US rates and monetary liquidity; no Cava validation implied",
            "execution_enabled": False,
        }
        if ok:
            payload["net_liquidity_million_usd"] = (
                factors["WALCL"]["value"] - factors["WDTGAL"]["value"] - factors["RRPONTSYD"]["value"] * 1000
            )
            prior_net = factors["WALCL"]["prior_value"] - factors["WDTGAL"]["prior_value"] - factors["RRPONTSYD"]["prior_value"] * 1000
            change = payload["net_liquidity_million_usd"] - prior_net
            payload["liquidity_change_4w_million_usd"] = change
            direction = lambda value: "rising" if value > 0 else "falling" if value < 0 else "unchanged"
            for symbol, row in factors.items():
                row["direction_4w"] = direction(row["change_4w"])
                row["unit"] = "percent" if symbol == "EFFR" else "billion USD" if symbol == "RRPONTSYD" else "million USD"
            payload["interpretation"] = {
                "kind": "INFERENCE",
                "liquidity": "improving" if change > 0 else "contracting" if change < 0 else "stable",
                "rates": direction(rates),
                "summary": f"Net liquidity is {direction(change)} over four weeks; effective policy rates are {direction(rates)}. The rates-based regime is {regime}.",
                "limitations": "Liquidity components have different observation dates; this is a balance-sheet measure, not a causal estimate or trade signal.",
            }
        previous = self.store.load_state("macro_material") if self.store else None
        changes = []
        if ok:
            if not previous or previous.get("regime") != regime:
                changes.append("initial_state" if not previous else "regime_changed")
            if previous:
                old_net = previous.get("net_liquidity_million_usd", 0)
                if abs(payload["net_liquidity_million_usd"] - old_net) >= max(abs(old_net) * .01, 50_000):
                    changes.append("liquidity_material_change")
                if abs(factors["EFFR"]["value"] - previous.get("rate", factors["EFFR"]["value"])) >= .25:
                    changes.append("rates_material_change")
                if payload["interpretation"]["liquidity"] != previous.get("liquidity_direction"):
                    changes.append("liquidity_direction_changed")
            if payload["net_liquidity_million_usd"] <= 0 and (not previous or previous.get("net_liquidity_million_usd", 1) > 0):
                changes.append("nonpositive_net_liquidity")
        payload["material_change"] = {"changed": bool(changes), "reasons": changes,
                                      "basis": "versus last material state; liquidity >= max(1%, USD 50bn), rate >= 25bp, regime/direction changes"}
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
            decision_time=decided,
            started_at=started,
            completed_at=decided,
            mode=Mode.LIVE,
            payload=payload,
            evidence=tuple(evidence),
            warnings=tuple(warnings),
            presentation={"market_result": bool(changes), "silent": not bool(changes), "diagnostic_only": False},
            reasons=() if ok else (ResearchReason(
                ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE if failed else ReasonCode.REQUIRED_EVIDENCE_MISSING,
                tuple(f"{symbol}:{row['status']}:{row.get('failure_kind', 'fresh PIT observation')}"
                      for symbol, row in factors.items() if row.get("status") != "OK"), True),),
        )
        if self.store:
            self.store.save_result(result)
            self.store.save_context("macro", payload)
            if ok and changes:
                self.store.save_state("macro_material", {
                    "regime": regime, "rate": factors["EFFR"]["value"],
                    "net_liquidity_million_usd": payload["net_liquidity_million_usd"],
                    "liquidity_direction": payload["interpretation"]["liquidity"],
                    "decision_time": iso(decided),
                })
        return result
