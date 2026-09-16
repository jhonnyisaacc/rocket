"""Multi-factor stock-short research. Bearish macro alone cannot select."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
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
_ISM_SHORT_FACTORS = (
    "ism_contracting",
    "technical_breakdown",
    "company_fundamentals",
)
_V2_STATES = ("RESEARCH", "WATCH", "ARMED", "TRIGGERED", "BLOCKED", "REJECTED")
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


def _ism_contracting(row: Mapping[str, Any]) -> bool | None:
    explicit = row.get("ism_contracting")
    if explicit is not None:
        return _flag(explicit)
    sources = row.get("candidate_sources")
    if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
        return None
    directions = {
        str(source.get("direction") or "").strip().lower()
        for source in sources
        if isinstance(source, Mapping)
    }
    if "short" in directions:
        return True
    return False if directions else None


def score_ism_short_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    """Small, explainable ISM short gate using the canonical live inputs.

    ISM supplies the contracting-industry signal, Yahoo supplies the price
    breakdown, and FMP supplies the bearish company-fundamentals flag (currently
    derived from its EPS-growth field). Optional valuation support remains a
    safety veto when the provider has it.
    """
    ticker = str(row.get("ticker") or row.get("asset") or "").strip().upper()
    factors = {
        "ism_contracting": _ism_contracting(row),
        "technical_breakdown": None if row.get("technical_breakdown") is None else _flag(row.get("technical_breakdown")),
        "company_fundamentals": None if row.get("company_fundamentals") is None else _flag(row.get("company_fundamentals")),
    }
    missing = [name for name, value in factors.items() if value is None]
    if missing:
        reason, selected = "insufficient_evidence", False
    elif row.get("valuation_support") is True:
        reason, selected = "valuation_support", False
    elif not factors["ism_contracting"]:
        reason, selected = "ism_not_contracting", False
    elif not factors["technical_breakdown"]:
        reason, selected = "technical_breakdown_missing", False
    elif not factors["company_fundamentals"]:
        reason, selected = "fundamentals_not_bearish", False
    else:
        reason, selected = None, True
    return {
        "asset": ticker,
        "direction": "short",
        "strategy": "ism_simple",
        "factors": factors,
        "factor_states": {name: "UNKNOWN" if value is None else "OBSERVED" for name, value in factors.items()},
        "missing_required_factors": missing,
        "factor_count": sum(value is True for value in factors.values()),
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


def _observed_deterioration(row: Mapping[str, Any]) -> bool | None:
    flags: list[bool] = []
    for key in ("eps_revision_30d", "revenue_revision_30d"):
        value = str(row.get(key) or "").upper()
        if value == "DETERIORATING":
            flags.append(True)
        elif value in {"IMPROVING", "FLAT"}:
            flags.append(False)
    quality = row.get("cash_flow_quality")
    quality_state = quality.get("state") if isinstance(quality, Mapping) else quality
    if str(quality_state or "").upper() == "DETERIORATING":
        flags.append(True)
    elif str(quality_state or "").upper() in {"IMPROVING", "FLAT"}:
        flags.append(False)
    fundamentals = None if row.get("company_fundamentals") is None else _flag(row.get("company_fundamentals"))
    if fundamentals is True:
        flags.append(True)
    elif fundamentals is False:
        flags.append(False)
    if not flags:
        return None
    return any(flags)


def score_shorts_v2(
    row: Mapping[str, Any],
    *,
    relative_threshold: float = 0.0,
    require_failed_retest: bool = False,
    rr_min: float | None = None,
) -> dict[str, Any]:
    """ISM selects the universe; deterioration filters; technicals time the setup."""
    from rocket.providers.short_quality import relative_weakness_flag, risk_reward
    from rocket.providers.tokenized_equities import RESEARCH_ELIGIBLE

    ticker = str(row.get("ticker") or row.get("asset") or "").strip().upper()
    ism = _ism_contracting(row)
    deterioration = _observed_deterioration(row)
    relative = relative_weakness_flag(row, threshold=relative_threshold)
    breakdown = None if row.get("technical_breakdown") is None else _flag(row.get("technical_breakdown"))
    retest = None if row.get("failed_retest") is None else _flag(row.get("failed_retest"))
    valuation_veto = row.get("valuation_support") is True
    regime = str(row.get("regime") or row.get("macro_regime") or "UNKNOWN").upper()
    if regime in {"RISK_OFF", "BEARISH", "CONTRACTION"}:
        regime = "SHORT_FRIENDLY"
    elif regime in {"RISK_ON", "BULLISH"}:
        regime = "SHORT_HOSTILE"
    elif regime not in {"SHORT_FRIENDLY", "SHORT_HOSTILE", "NEUTRAL"}:
        regime = "UNKNOWN"
    price = row.get("current_price")
    if price is None:
        price = row["entry"].get("level") if isinstance(row.get("entry"), Mapping) else row.get("entry")
    stop = row.get("invalidation")
    if isinstance(stop, Mapping):
        stop = stop.get("level")
    rr = row.get("risk_reward") if isinstance(row.get("risk_reward"), Mapping) else risk_reward(
        price,
        stop,
        row.get("target"),
    )
    rr_value = rr.get("reward_to_risk")
    rr_ok = None if rr_value in (None, "UNKNOWN") else (rr_value >= rr_min if rr_min is not None else True)
    catalysts = row.get("catalysts") if isinstance(row.get("catalysts"), list) else []
    if not catalysts and row.get("catalyst") not in (None, "", "UNKNOWN", "unknown", "none"):
        catalysts = [row.get("catalyst")]

    if valuation_veto:
        state, reason = "BLOCKED", "valuation_support"
    elif ism is None or deterioration is None:
        state, reason = "RESEARCH", "insufficient_evidence"
    elif not ism:
        state, reason = "REJECTED", "ism_not_contracting"
    elif not deterioration:
        state, reason = "REJECTED", "fundamentals_not_bearish"
    elif relative is None:
        state, reason = "RESEARCH", "relative_strength_unknown"
    elif not relative:
        state, reason = "REJECTED", "relative_strength_not_weak"
    elif rr_min is not None and rr_ok is None:
        state, reason = "RESEARCH", "reward_to_risk_unknown"
    elif rr_min is not None and rr_ok is False:
        state, reason = "BLOCKED", "reward_to_risk_below_threshold"
    elif breakdown is None:
        state, reason = "WATCH", "technical_breakdown_unknown"
    elif not breakdown:
        state, reason = "WATCH", None
    elif require_failed_retest and retest is None:
        state, reason = "ARMED", "failed_retest_unknown"
    elif require_failed_retest and not retest:
        state, reason = "ARMED", None
    else:
        state, reason = "TRIGGERED", None

    risk_class = {
        "SHORT_FRIENDLY": "standard",
        "NEUTRAL": "elevated",
        "SHORT_HOSTILE": "unattractive",
    }.get(regime, "UNKNOWN")
    factors = {
        "ism_contracting": ism,
        "company_deterioration": deterioration,
        "relative_weakness": relative,
        "technical_breakdown": breakdown,
        "failed_retest": retest,
        "catalyst": catalysts[0] if catalysts else None,
        "regime": None if regime == "UNKNOWN" else regime,
        "reward_to_risk": rr_value,
        "valuation_support": None if row.get("valuation_support") is None else bool(row.get("valuation_support")),
    }
    return {
        "asset": ticker,
        "direction": "short",
        "strategy": "shorts_v2",
        "state": state,
        "selected": state == "TRIGGERED",
        "rejection_reason": reason,
        "factors": factors,
        "factor_states": {
            name: "UNKNOWN" if factors.get(name) in (None, "UNKNOWN") else "OBSERVED"
            for name in factors
        },
        "missing_required_factors": [name for name, value in (("ism_contracting", ism), ("company_deterioration", deterioration)) if value is None],
        "research_eligibility": row.get("research_eligibility") or RESEARCH_ELIGIBLE,
        "execution_eligibility": row.get("execution_eligibility") or "UNKNOWN",
        "regime": regime,
        "risk_class": risk_class,
        "catalysts": catalysts,
        "risk_reward": rr,
        "relative_vs_sector": row.get("relative_vs_sector"),
        "relative_vs_market": row.get("relative_vs_market"),
        "eps_revision_30d": row.get("eps_revision_30d"),
        "revenue_revision_30d": row.get("revenue_revision_30d"),
        "cash_flow_quality": row.get("cash_flow_quality"),
        "current_price": row.get("current_price"),
        "technical_setup": row.get("technical_setup"),
        "entry": rr.get("entry") or row.get("entry"),
        "invalidation": rr.get("invalidation") or row.get("invalidation"),
        "target": rr.get("target") or row.get("target"),
        "research_only": True,
        "candidate_id": row.get("candidate_id"),
        "sources": row.get("candidate_sources", []),
        "why_here": [s.get("thesis") or s.get("reason") for s in row.get("candidate_sources", [])],
        "fundamentals": {k: row.get(k) for k in ("pe_ttm", "eps_growth", "eps_growth_basis", "fundamentals_source")},
        "tokenized": row.get("tokenized"),
        "relative_threshold": relative_threshold,
        "require_failed_retest": require_failed_retest,
        "rr_min": rr_min,
    }


class ShortsWorkflow:
    name = WORKFLOW

    def __init__(self, *, store: ResearchStore | None = None):
        self.store = store

    def scan_live(self, *, now=None, inputs=None, snapshot_fetcher=None, strategy="ism_simple"):
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
        scorer = score_shorts_v2 if strategy == "shorts_v2" else score_ism_short_candidate if strategy == "ism_simple" else score_candidate
        return self.scan(rows, now=now, scorer=scorer, strategy=strategy)

    def _missing_candidates(self, decided):
        result = ResearchResult(workflow=WORKFLOW, status=ResearchStatus.INSUFFICIENT_EVIDENCE,
                                operational=OperationalReport(OperationalStatus.HEALTHY), decision_time=decided, started_at=decided,
                                mode=Mode.LIVE, payload={"universe_scanned": 0, "final_candidates": [], "execution_enabled": False},
                                reasons=(ResearchReason(ReasonCode.CALLER_STATE_MISSING, ("current canonical bearish candidate acquisition",)),))
        if self.store:
            self.store.save_result(result)
        return result

    def scan(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        now: datetime | None = None,
        scorer: Callable[[Mapping[str, Any]], dict[str, Any]] = score_candidate,
        strategy: str = "generic",
    ) -> ResearchResult:
        decided = now or datetime.now(UTC)
        candidates: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        watchlist: list[dict[str, Any]] = []
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
                candidate = scorer(row)
                evidence.append(
                    Evidence(
                        source=str(row.get("source") or "short_snapshot"),
                        reference=f"short-{index + 1}",
                        claim=f"{ticker} {strategy} short research snapshot",
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
            if candidate.get("state") in {"WATCH", "ARMED", "TRIGGERED"}:
                watchlist.append(candidate)
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
        elif operational is OperationalStatus.UNAVAILABLE:
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
        elif strategy == "shorts_v2":
            pit_fail = {"invalid_input", "availability_unknown", "available_after_decision_time",
                        "stale_or_future_observation", "observation_or_provenance_unknown"}
            if any(row.get("reason") in pit_fail for row in rejected):
                research = ResearchStatus.INSUFFICIENT_EVIDENCE
            elif watchlist or any(row.get("state") in {"REJECTED", "BLOCKED", "ARMED", "WATCH"} for row in rejected):
                research = ResearchStatus.NO_SETUP
            else:
                research = ResearchStatus.INSUFFICIENT_EVIDENCE
        elif any(row.get("reason") in {"insufficient_evidence", "invalid_input", "availability_unknown", "available_after_decision_time", "stale_or_future_observation", "observation_or_provenance_unknown"} for row in rejected):
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
                "strategy": strategy,
                "final_candidates": candidates,
                "watchlist": watchlist,
                "rejected_candidates": rejected,
                "factor_definition": list(_ISM_SHORT_FACTORS if strategy == "ism_simple" else _FACTORS if strategy != "shorts_v2" else (
                    "ism_contracting",
                    "company_deterioration",
                    "relative_weakness",
                    "technical_breakdown",
                    "failed_retest",
                    "regime",
                    "reward_to_risk",
                )),
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
