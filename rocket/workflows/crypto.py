"""One crypto futures engine: top-100 universe → funnel → optional Cava overlay."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
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
from rocket.pit import parse_datetime
from rocket.store import ResearchStore
from rocket.workflows.macro import macro_is_usable

WORKFLOW_SCAN = "crypto.scan"
WORKFLOW_EVAL = "crypto.evaluate"
WORKFLOW_MISSED = "crypto.missed"
UNIVERSE_SIZE = 100


def _asset_key(candidate: Mapping[str, Any]) -> str:
    canonical = candidate.get("canonical_asset_id")
    if canonical:
        return "canonical:" + str(canonical).lower()
    chain, address = candidate.get("chain_id"), candidate.get("contract_address")
    if chain and address:
        return f"{chain}:{address}"
    key = candidate.get("asset_key")
    return str(key) if key and ":" in str(key) else "unknown"


def _direction(candidate: Mapping[str, Any]) -> str | None:
    setup = candidate.get("setup_validation")
    if isinstance(setup, Mapping) and setup.get("direction") in {"long", "short"}:
        return str(setup["direction"])
    return None


def cot_regime_passes(regime: str, direction: str | None) -> bool:
    normalized = regime.strip().lower()
    if normalized not in {"bullish", "bearish", "neutral"} or direction not in {"long", "short"}:
        return False
    if normalized == "bullish":
        return direction == "long"
    if normalized == "bearish":
        return direction == "short"
    return True


def build_funnel(
    payload: Mapping[str, Any],
    *,
    macro_context: Mapping[str, Any] | None = None,
    cot_regime: str = "unknown",
    cot_context: Mapping[str, Any] | None = None,
    context_decision_time: datetime | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Evidence]]:
    counts = {
        "universe": 0,
        "eligible": 0,
        "liquid": 0,
        "momentum_pass": 0,
        "derivatives_pass": 0,
        "macro_pass": 0,
        "cot_pass": 0,
        "final_candidates": 0,
        "invalid_observations": 0,
        "unavailable_instruments": 0,
    }
    final_candidates: list[dict[str, Any]] = []
    evidence: list[Evidence] = []
    unique_members: set[str] = set()
    macro_checks: list[bool] = []
    effective_cot = str((cot_context or {}).get("regime") if cot_context is not None else cot_regime).lower()
    if effective_cot not in {"bullish", "bearish", "neutral"}:
        effective_cot = "unknown"
    if cot_context is not None and cot_context.get("status") not in {"OK", "OVERRIDE"}:
        effective_cot = "unknown"
    for observation in payload.get("observations") or []:
        if not isinstance(observation, Mapping):
            continue
        observation_time = parse_datetime(observation.get("observation_timestamp"))
        if observation_time is None:
            counts["invalid_observations"] += 1
            continue
        macro_checks.append(macro_is_usable(macro_context, context_decision_time or observation_time))
        members = observation.get("universe_members_deduplicated") or observation.get("universe_members") or []
        for member in members:
            if isinstance(member, Mapping):
                member_key = _asset_key(member)
            else:
                member_key = str(member).strip().lower()
            if member_key and member_key != "unknown":
                unique_members.add(member_key)
        counts["universe"] = len(unique_members)
        evidence.append(
            Evidence(
                source=str(observation.get("source") or "crypto.universe"),
                reference=f"crypto-universe-{observation_time.isoformat()}",
                claim=f"The point-in-time universe contained {len(members)} deduplicated members",
                kind=EvidenceKind.FACT,
                event_time=observation_time,
                available_at=parse_datetime(observation.get("source_timestamp")) or observation_time,
                retrieved_at=observation_time,
                decision_time=observation_time,
                provenance=Provenance.PROVIDER_RESULT,
            )
        )
        for raw_candidate in observation.get("candidates") or []:
            if not isinstance(raw_candidate, Mapping):
                continue
            state = raw_candidate.get("ranking_state")
            liquidity = raw_candidate.get("liquidity") if isinstance(raw_candidate.get("liquidity"), Mapping) else {}
            eligible = state == "ELIGIBLE"
            liquid = liquidity.get("state") == "PASS"
            setup = raw_candidate.get("setup_validation")
            setup_valid = bool(isinstance(setup, Mapping) and setup.get("valid") is True)
            direction = _direction(raw_candidate)
            macro_pass = macro_checks[-1]
            if macro_pass and (macro_context or {}).get("contract") == "current_macro_v1":
                macro_pass = cot_regime_passes(str(macro_context.get("regime")), direction)
            features = raw_candidate.get("features") if isinstance(raw_candidate.get("features"), Mapping) else {}
            if state == "UNKNOWN" and not features:
                counts["unavailable_instruments"] += 1
                continue
            available = parse_datetime(features.get("data_timestamp"))
            if _asset_key(raw_candidate) == "unknown" or available is None or available > observation_time:
                counts["invalid_observations"] += 1
                continue
            cot_pass = cot_regime_passes(effective_cot, direction)
            if eligible:
                counts["eligible"] += 1
                counts["momentum_pass"] += 1
            if liquid:
                counts["liquid"] += 1
                counts["derivatives_pass"] += 1
            if macro_pass and eligible and liquid:
                counts["macro_pass"] += 1
            if cot_pass and eligible and liquid:
                counts["cot_pass"] += 1
            if not (eligible and liquid and setup_valid and macro_pass and cot_pass):
                continue
            candidate = {
                "asset": raw_candidate.get("symbol"),
                "asset_key": _asset_key(raw_candidate),
                "direction": direction,
                "entry_research_zone": setup.get("entry_zone") if isinstance(setup, Mapping) else None,
                "invalidation": setup.get("invalidation") if isinstance(setup, Mapping) else None,
                "rank_score": raw_candidate.get("rank_score"),
                "observation_timestamp": observation_time.isoformat(),
            }
            final_candidates.append(candidate)
            evidence.append(
                Evidence(
                    source=str(features.get("data_source") or "crypto.futures"),
                    reference=f"crypto-{_asset_key(raw_candidate)}-{observation_time.isoformat()}",
                    claim="Momentum, market structure, and derivatives filters were evaluated",
                    kind=EvidenceKind.INFERENCE,
                    event_time=observation_time,
                    available_at=available,
                    retrieved_at=observation_time,
                    decision_time=observation_time,
                    provenance=Provenance.PROVIDER_RESULT,
                    metadata={"asset": _asset_key(raw_candidate)},
                )
            )
    counts["final_candidates"] = len(final_candidates)
    funnel = {
        **counts,
        "cot_regime": effective_cot,
        "cot_scope": "market/regime context; no per-altcoin COT signal",
        "macro_context_validated": bool(macro_checks) and all(macro_checks),
        "universe_policy": "top_100_market_cap_plus_liquid_perps",
        "universe_size_target": UNIVERSE_SIZE,
    }
    return funnel, final_candidates, evidence


def analyze_missed_moves(
    scan_payload: Mapping[str, Any],
    outcomes: list[Mapping[str, Any]],
    *,
    move_threshold: float = 0.20,
) -> list[dict[str, Any]]:
    selected = {
        _asset_key(candidate)
        for candidate in (scan_payload.get("final_candidates") or [])
        if isinstance(candidate, Mapping)
    }
    candidate_by_key: dict[str, Mapping[str, Any]] = {}
    for observation in scan_payload.get("observations") or []:
        if not isinstance(observation, Mapping):
            continue
        for candidate in observation.get("candidates") or []:
            if isinstance(candidate, Mapping):
                candidate_by_key[_asset_key(candidate)] = candidate
    missed: list[dict[str, Any]] = []
    for outcome in outcomes:
        if not isinstance(outcome, Mapping):
            continue
        try:
            move = float(outcome.get("forward_return"))
        except (TypeError, ValueError):
            continue
        key = _asset_key(outcome)
        if not math.isfinite(move) or move < move_threshold or key in selected:
            continue
        candidate = candidate_by_key.get(key) if key != "unknown" else None
        decision_time = parse_datetime((candidate or {}).get("observation_timestamp") or outcome.get("decision_time"))
        available_at = parse_datetime(outcome.get("information_available_at"))
        if available_at is None or decision_time is None or key == "unknown":
            information_state = "UNKNOWN"
        else:
            information_state = "BEFORE_MOVE" if available_at <= decision_time else "AFTER_DECISION"
        missed.append(
            {
                "asset": outcome.get("asset") or outcome.get("symbol"),
                "asset_key": key,
                "later_move": move,
                "information_existed_before_move": information_state,
                "hindsight_data_used_as_signal": False,
            }
        )
    return missed


class CryptoWorkflow:
    name = WORKFLOW_SCAN

    def __init__(self, *, store: ResearchStore | None = None):
        self.store = store

    def scan_payload(
        self,
        replay_payload: Mapping[str, Any],
        *,
        macro_context: Mapping[str, Any] | None = None,
        cot_regime: str = "unknown",
        cot_context: Mapping[str, Any] | None = None,
        cava_context: Mapping[str, Any] | None = None,
        mode: Mode = Mode.REPLAY,
        now: datetime | None = None,
    ) -> ResearchResult:
        observations = replay_payload.get("observations") or []
        times = [parse_datetime(row.get("observation_timestamp")) for row in observations if isinstance(row, Mapping)]
        known = [stamp for stamp in times if stamp is not None]
        if mode is Mode.REPLAY:
            if not known:
                raise ValueError("REPLAY requires a historical observation timestamp")
            now = max(known)
        elif now is None:
            now = max(known) if known else datetime.now(UTC)
        funnel, candidates, evidence = build_funnel(
            replay_payload,
            macro_context=macro_context,
            cot_regime=cot_regime,
            cot_context=cot_context,
            context_decision_time=now if mode is Mode.LIVE else None,
        )
        evidence = [replace(item, decision_time=now) for item in evidence]
        cava_status = "unavailable"
        if cava_context:
            cava_status = "available" if cava_context.get("validated") is True else "insufficient"
        funnel["cava_context_status"] = cava_status
        warnings = []
        if not funnel["macro_context_validated"]:
            warnings.append("core macro evidence unavailable")
        if funnel["cot_regime"] not in {"bullish", "bearish", "neutral"}:
            warnings.append("COT regime unavailable; COT is not applied as an asset-level signal")
        if candidates:
            research = ResearchStatus.SETUP_FOUND
        elif warnings or funnel.get("invalid_observations"):
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
        else:
            research = ResearchStatus.NO_SETUP
        operational = OperationalStatus.HEALTHY
        if replay_payload.get("provider_status") == "UNAVAILABLE":
            operational = OperationalStatus.UNAVAILABLE
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
        result = ResearchResult(
            workflow=WORKFLOW_SCAN,
            status=research,
            operational=OperationalReport(
                status=operational,
                providers=(ProviderHealth(name="crypto.universe", status=operational, retrieved_at=now),),
            ),
            decision_time=now,
            started_at=now,
            completed_at=now,
            mode=mode,
            payload={
                "mode": mode.value,
                "funnel": funnel,
                "macro_context": dict(macro_context or {}),
                "cava_context_status": cava_status,
                "final_candidates": candidates,
                "observations": list(observations),
                "execution_enabled": False,
                "loaded_live_context": False,
            },
            evidence=tuple(evidence),
            warnings=tuple(warnings),
        )
        if self.store:
            self.store.save_result(result)
        return result

    def scan_from_fixture(self, path: Path, *, cot_regime: str = "unknown") -> ResearchResult:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return self.scan_payload(payload, cot_regime=cot_regime, mode=Mode.REPLAY)

    def scan_live(
        self,
        *,
        now: datetime | None = None,
        macro_context: Mapping[str, Any] | None = None,
        universe=None,
        cot_regime: str = "unknown",
    ) -> ResearchResult:
        from rocket.providers.coingecko import fetch_top_universe
        from rocket.workflows.macro import MacroWorkflow

        observed = now or datetime.now(UTC)
        discovery = universe or fetch_top_universe()
        if discovery.status is not OperationalStatus.HEALTHY:
            result = ResearchResult(
                workflow=WORKFLOW_SCAN,
                status=ResearchStatus.INSUFFICIENT_EVIDENCE,
                operational=OperationalReport(
                    status=OperationalStatus.UNAVAILABLE,
                    providers=(
                        ProviderHealth(
                            name="coingecko",
                            status=OperationalStatus.UNAVAILABLE,
                            failure_kind=discovery.failure_kind,
                            retrieved_at=observed,
                        ),
                    ),
                ),
                decision_time=observed,
                started_at=observed,
                completed_at=observed,
                mode=Mode.LIVE,
                payload={
                    "mode": "LIVE",
                    "funnel": {"universe": 0, "final_candidates": 0, "universe_size_target": UNIVERSE_SIZE},
                    "final_candidates": [],
                    "execution_enabled": False,
                },
                warnings=("live current-universe discovery is unavailable",),
            )
            if self.store:
                self.store.save_result(result)
            return result
        if macro_context is None:
            macro_context = MacroWorkflow(store=self.store).run(now=observed).payload
        cava = self.store.load_context("cava") if self.store else None
        observation = {
            "observation_timestamp": observed.isoformat(),
            "source": "live:CoinGecko",
            "source_timestamp": observed.isoformat(),
            "universe_members_deduplicated": list(discovery.records),
            "candidates": [],
        }
        return self.scan_payload(
            {"observations": [observation], "window": {"mode": "LIVE"}},
            macro_context=macro_context,
            cot_regime=cot_regime,
            cava_context=cava,
            mode=Mode.LIVE,
            now=observed,
        )

    def evaluate(self, scan_result: ResearchResult, outcomes: list[Mapping[str, Any]]) -> ResearchResult:
        selected = scan_result.payload.get("final_candidates") or []
        evaluated = []
        for outcome in outcomes:
            if not isinstance(outcome, Mapping):
                continue
            key = _asset_key(outcome)
            if key == "unknown" or key not in {_asset_key(item) for item in selected if isinstance(item, Mapping)}:
                continue
            try:
                forward = float(outcome["forward_return"])
            except (KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(forward):
                continue
            evaluated.append({**dict(outcome), "asset_key": key, "hit": forward >= 0})
        now = datetime.now(UTC)
        result = ResearchResult(
            workflow=WORKFLOW_EVAL,
            status=ResearchStatus.INSUFFICIENT_EVIDENCE,
            operational=OperationalReport(status=OperationalStatus.HEALTHY),
            decision_time=now,
            started_at=now,
            completed_at=now,
            payload={
                "strategy_state": "EXPERIMENTAL",
                "metrics": {
                    "evaluated_count": len(evaluated),
                    "hit_rate": (sum(item["hit"] for item in evaluated) / len(evaluated)) if evaluated else None,
                },
                "outcomes": evaluated,
                "source_scan_run_id": scan_result.run_id,
                "execution_enabled": False,
            },
            warnings=("evaluation is research evidence; Rocket never writes VALIDATED",),
        )
        if self.store:
            self.store.save_result(result)
        return result

    def missed(self, scan_result: ResearchResult, outcomes: list[Mapping[str, Any]]) -> ResearchResult:
        missed = analyze_missed_moves(scan_result.payload, outcomes)
        now = datetime.now(UTC)
        result = ResearchResult(
            workflow=WORKFLOW_MISSED,
            status=ResearchStatus.NO_SETUP if not missed else ResearchStatus.INSUFFICIENT_EVIDENCE,
            operational=OperationalReport(status=OperationalStatus.HEALTHY),
            decision_time=now,
            started_at=now,
            completed_at=now,
            payload={"missed_moves": missed, "hindsight_data_used_as_signal": False, "execution_enabled": False},
            warnings=("Missed moves require human review for systematic blind spots.",),
        )
        if self.store:
            self.store.save_result(result)
        return result
