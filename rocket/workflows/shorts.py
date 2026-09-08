"""Multi-factor stock-short research. Bearish macro alone cannot select."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
from rocket.pit import parse_datetime
from rocket.store import ResearchStore

WORKFLOW = "shorts"
# Catalyst is optional: there is no live catalyst provider. Missing stays UNKNOWN.
_FACTORS = (
    "macro_regime",
    "sector_weakness",
    "earnings_revision_deterioration",
    "valuation_support",
    "technical_breakdown",
    "catalyst",
    "positioning_crowding",
    "company_fundamentals",
)
UNIVERSE = {}  # Production candidates come from the shared research index.


def _flag(value: object) -> bool | None:
    if isinstance(value, str):
        value = value.strip().lower()
        if value in {"1", "true", "yes", "y", "bearish", "weak", "high"}:
            return True
        return False if value in {"0", "false", "no", "n", "bullish", "strong", "low"} else None
    return bool(value) if isinstance(value, (bool, int, float)) and value in (0, 1) else None


def score_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    ticker = str(row.get("ticker") or row.get("asset") or "").strip().upper()
    macro = str(row.get("macro_regime") or "").strip().lower()
    fundamentals = row.get("company_fundamentals")
    factors = {
        "macro_regime": macro or None,
        "sector_weakness": None if row.get("sector_weakness") is None else _flag(row.get("sector_weakness")),
        "earnings_revision_deterioration": None if row.get("earnings_revision_deterioration") is None else _flag(row.get("earnings_revision_deterioration")),
        "valuation_support": None if row.get("valuation_support") is None else _flag(row.get("valuation_support")),
        "technical_breakdown": None if row.get("technical_breakdown") is None else _flag(row.get("technical_breakdown")),
        "catalyst": None if str(row.get("catalyst") or "").strip().lower() in {"", "unknown", "none", "unavailable"} else str(row["catalyst"]).strip(),
        "positioning_crowding": None if row.get("positioning_crowding") is None else _flag(row.get("positioning_crowding")),
        "company_fundamentals": None if fundamentals is None else _flag(fundamentals),
    }
    non_macro = sum(
        factors[name] is True if name == "company_fundamentals" else bool(factors[name])
        for name in _FACTORS
        if name not in {"macro_regime", "valuation_support"}
    )
    total = non_macro + int(macro in {"bearish", "risk_off", "contraction"})
    missing = [name for name in dict.fromkeys(("company_fundamentals", "technical_breakdown", *row.get("required_factors", []))) if factors.get(name, row.get(name)) is None]
    if missing:
        reason, selected = "insufficient_evidence", False
    elif factors["valuation_support"]:
        reason, selected = "valuation_support", False
    elif total < 3:
        reason = "macro_only" if macro in {"bearish", "risk_off", "contraction"} and non_macro < 2 else "insufficient_factors"
        selected = False
    elif non_macro < 2:
        reason, selected = "macro_only", False
    else:
        reason, selected = None, True
    return {
        "asset": ticker,
        "direction": "short",
        "factors": factors,
        "factor_states": {name: "UNKNOWN" if factors.get(name) is None else "OBSERVED" for name in _FACTORS},
        "missing_required_factors": missing,
        "factor_count": total,
        "selected": selected,
        "rejection_reason": reason,
        "research_only": True,
        "candidate_id": row.get("candidate_id"),
        "sources": row.get("candidate_sources", []),
        "why_here": [s.get("thesis") or s.get("reason") for s in row.get("candidate_sources", [])],
        "current_price": row.get("current_price"),
        "technical_setup": row.get("technical_setup"),
        "fundamentals": {k: row.get(k) for k in ("pe_ttm", "eps_growth", "eps_growth_basis", "fundamentals_source")},
        "entry": row.get("entry"),
        "invalidation": row.get("invalidation"),
    }


class ShortsWorkflow:
    name = WORKFLOW

    def __init__(self, *, store: ResearchStore | None = None):
        self.store = store

    def scan_live(self, *, now=None, inputs=None, snapshot_fetcher=None):
        from rocket.candidates import bearish_inputs
        from rocket.providers.shorts import acquire_short_snapshot, live_fundamentals_fetcher
        decided = now or datetime.now(UTC)
        if inputs is None:
            state = self.store.load_state("research_candidates") if self.store else None
            if state is None:
                return self._missing_candidates(decided)
            inputs = bearish_inputs(self.store, decided)
            if not inputs:
                try:
                    updated = parse_datetime(state.get("updated_at"))
                    if not updated or not timedelta(0) <= decided - updated <= timedelta(days=1):
                        return self._missing_candidates(decided)
                except ValueError:
                    return self._missing_candidates(decided)
        if not inputs:
            result = ResearchResult(workflow=WORKFLOW, status=ResearchStatus.NO_SETUP,
                                    operational=OperationalReport(OperationalStatus.HEALTHY),
                                    decision_time=decided, started_at=decided, mode=Mode.LIVE,
                                    payload={"universe_scanned": 0, "final_candidates": [], "execution_enabled": False,
                                             "summary": "Shorts scan: no valid setup found today.",
                                             "candidate_source": "canonical research candidates"},
                                    presentation={"market_result": False, "silent": False, "diagnostic_only": False})
            if self.store:
                self.store.save_result(result)
            return result
        universe = {r["ticker"]: r.get("sector_etf") for r in inputs}
        rows = (snapshot_fetcher or acquire_short_snapshot)(universe=universe,
                                                            fundamentals=live_fundamentals_fetcher(), now=now)
        by_ticker = {r["ticker"]: r for r in inputs}
        for row in rows:
            seed = by_ticker[row["ticker"]]
            row["candidate_sources"] = seed["sources"]
            row["candidate_id"] = seed["candidate_id"]
        return self.scan(rows, now=now)

    def _missing_candidates(self, decided):
        result = ResearchResult(workflow=WORKFLOW, status=ResearchStatus.INSUFFICIENT_EVIDENCE,
                                operational=OperationalReport(OperationalStatus.HEALTHY), decision_time=decided, started_at=decided,
                                mode=Mode.LIVE, payload={"universe_scanned": 0, "final_candidates": [], "execution_enabled": False},
                                reasons=(ResearchReason(ReasonCode.CALLER_STATE_MISSING, ("current canonical bearish candidate acquisition",)),))
        if self.store:
            self.store.save_result(result)
        return result

    def scan(self, rows: Sequence[Mapping[str, Any]], *, now: datetime | None = None) -> ResearchResult:
        decided = now or datetime.now(UTC)
        candidates: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        evidence: list[Evidence] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                rejected.append({"row": index, "reason": "invalid_input"})
                continue
            ticker = str(row.get("ticker") or row.get("asset") or "").strip().upper()
            try:
                available_at = parse_datetime(row.get("available_at"))
                if not ticker:
                    raise ValueError("ticker is required")
                if available_at is None:
                    rejected.append({"asset": ticker or "UNKNOWN", "reason": "availability_unknown"})
                    continue
                if available_at > decided:
                    rejected.append({"asset": ticker, "reason": "available_after_decision_time"})
                    continue
                observed = parse_datetime(row.get("event_time"))
                if observed is None or not row.get("source"):
                    rejected.append({"asset": ticker, "reason": "observation_or_provenance_unknown"})
                    continue
                if observed > decided or decided - observed > timedelta(days=5):
                    rejected.append({"asset": ticker, "reason": "stale_or_future_observation"})
                    continue
                candidate = score_candidate(row)
                evidence.append(
                    Evidence(
                        source=str(row.get("source") or "short_snapshot"),
                        reference=f"short-{index + 1}",
                        claim=f"{ticker} multi-factor short research snapshot",
                        kind=EvidenceKind.FACT,
                        event_time=observed,
                        available_at=available_at,
                        retrieved_at=decided,
                        decision_time=decided,
                        provenance=Provenance.PROVIDER_RESULT,
                    )
                )
            except ValueError as exc:
                rejected.append({"asset": ticker or "UNKNOWN", "reason": "invalid_input", "detail": str(exc)})
                continue
            if candidate["selected"]:
                candidates.append(candidate)
            else:
                rejected.append({**candidate, "reason": candidate["rejection_reason"]})
        live = any(isinstance(row, Mapping) and row.get("acquisition_mode") == "LIVE" for row in rows)
        if live:
            if all(isinstance(row, Mapping) and row.get("provider_health") == "HEALTHY" for row in rows):
                operational = OperationalStatus.HEALTHY
            elif any(isinstance(row, Mapping) and row.get("provider_health") in {"HEALTHY", "PARTIAL"} for row in rows):
                operational = OperationalStatus.PARTIAL
            else:
                operational = OperationalStatus.UNAVAILABLE
        else:
            operational = OperationalStatus.HEALTHY
        if candidates:
            research = ResearchStatus.SETUP_FOUND
        elif operational is OperationalStatus.UNAVAILABLE or any(row.get("reason") in {"insufficient_evidence", "invalid_input", "availability_unknown", "available_after_decision_time", "stale_or_future_observation", "observation_or_provenance_unknown"} for row in rejected):
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
        elif rows and evidence:
            research = ResearchStatus.NO_SETUP
        else:
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
        warnings = (
            ("No point-in-time stock snapshots were supplied; no short research candidate was produced.",)
            if not rows
            else ("No multi-factor short setup passed; rejected candidates are retained for audit.",)
            if not candidates
            else ("Research candidate only; a bearish macro view alone is never sufficient and no execution is enabled.",)
        )
        result = ResearchResult(
            workflow=WORKFLOW,
            status=research,
            operational=OperationalReport(
                status=operational,
                providers=tuple(ProviderHealth.from_dict(p) for row in rows if isinstance(row, Mapping) for p in row.get("provider_attempts", []))
                or (ProviderHealth(name="shorts.live" if live else "shorts.replay", status=operational, retrieved_at=decided,
                                   coverage=f"{len(evidence)}/{len(rows)} eligible snapshots"),),
            ),
            decision_time=decided,
            started_at=decided,
            completed_at=decided,
            mode=Mode.LIVE if live else Mode.REPLAY,
            payload={
                "universe_scanned": len(rows),
                "acquisition_mode": "LIVE" if live else "REPLAY",
                "final_candidates": candidates,
                "rejected_candidates": rejected,
                "factor_definition": list(_FACTORS),
                "snapshots": list(rows),
                "execution_enabled": False,
                "summary": "Shorts scan: no valid setup found today." if research is ResearchStatus.NO_SETUP else None,
            },
            evidence=tuple(evidence),
            warnings=warnings,
            presentation={"market_result": bool(candidates), "silent": False, "diagnostic_only": False},
            reasons=(ResearchReason(ReasonCode.CALLER_STATE_MISSING if not rows
                                    else ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE if live and operational is not OperationalStatus.HEALTHY
                                    else ReasonCode.REQUIRED_EVIDENCE_MISSING,
                                    tuple(f"{r.get('asset', 'UNKNOWN')}:{r.get('reason')}:{','.join(r.get('missing_required_factors', []))}"
                                          for r in rejected) or ("caller stock snapshots",), live),)
            if research is ResearchStatus.INSUFFICIENT_EVIDENCE else (),
        )
        if self.store:
            self.store.save_result(result)
        return result
