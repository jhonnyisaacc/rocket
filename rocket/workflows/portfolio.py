"""Per-position review. Caller owns theses; wallet inventory is read-only evidence."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rocket.clock import equity_observation_fresh
from rocket.config import env
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
from rocket.pit import Availability, PointInTime, parse_datetime
from rocket.store import ResearchStore

WORKFLOW = "portfolio.review"


@dataclass(frozen=True)
class PositionState:
    ticker: str
    thesis: str = ""
    thesis_status: str = "RECORDED"
    thesis_reference: str | None = None
    source_strategy: str = "manual"
    candidate_status: str = "current"
    watch_target: float | None = None
    quantity: float | None = None
    mint: str | None = None


@dataclass(frozen=True)
class PortfolioState:
    source_path: str | None = None
    updated_at: str | None = None
    wallet_address: str | None = None
    ledger_history_complete: bool | None = None
    positions: tuple[PositionState, ...] = ()


def load_portfolio_state(path: Path) -> PortfolioState:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("portfolio state must be a JSON object")
    rows = payload.get("positions", [])
    if not isinstance(rows, list) or any(not isinstance(item, Mapping) or not str(item.get("ticker") or "").strip() for item in rows):
        raise ValueError("portfolio positions must be objects with caller-owned tickers")
    positions = tuple(
        PositionState(
            ticker=str(item.get("ticker") or "").strip().upper(),
            thesis=str(item.get("thesis") or ""),
            thesis_status=str(item.get("thesis_status") or "RECORDED"),
            thesis_reference=item.get("thesis_reference"),
            source_strategy=str(item.get("source_strategy") or "manual"),
            candidate_status=str(item.get("candidate_status") or "current"),
            watch_target=item.get("watch_target"),
            quantity=item.get("quantity") if item.get("quantity") is not None else item.get("shares"),
            mint=item.get("mint"),
        )
        for item in payload.get("positions") or []
        if isinstance(item, Mapping) and str(item.get("ticker") or "").strip()
    )
    return PortfolioState(
        source_path=str(path),
        updated_at=payload.get("updated_at"),
        wallet_address=payload.get("wallet_address") or payload.get("address"),
        ledger_history_complete=payload.get("ledger_history_complete"),
        positions=positions,
    )


def positive_number(value: Any) -> bool:
    try:
        return not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def apply_inventory(state: PortfolioState, records: Mapping[str, Mapping[str, Any]]) -> PortfolioState:
    """Update quantities on existing names only. Never create positions or overwrite theses."""
    updated = []
    for position in state.positions:
        row = records.get(position.ticker) or records.get(position.ticker.upper())
        quantity = position.quantity
        if isinstance(row, Mapping) and (positive_number(row.get("quantity")) or
                                        row.get("quantity") == 0 and row.get("zero_confirmed") is True):
            quantity = float(row["quantity"])
        updated.append(
            PositionState(
                ticker=position.ticker,
                thesis=position.thesis,
                thesis_status=position.thesis_status,
                thesis_reference=position.thesis_reference,
                source_strategy=position.source_strategy,
                candidate_status=position.candidate_status,
                watch_target=position.watch_target,
                quantity=quantity,
                mint=position.mint,
            )
        )
    return PortfolioState(
        source_path=state.source_path,
        updated_at=state.updated_at,
        wallet_address=state.wallet_address,
        ledger_history_complete=state.ledger_history_complete,
        positions=tuple(updated),
    )


def review_positions(
    state: PortfolioState,
    evidence_by_ticker: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    now: datetime | None = None,
    inventory_status: OperationalStatus | None = None,
    pending_review: Sequence[Mapping[str, Any]] = (),
    extra_warnings: Sequence[str] = (),
) -> ResearchResult:
    evidence_by_ticker = evidence_by_ticker or {}
    decisions: list[dict[str, Any]] = []
    evidence: list[Evidence] = []
    decision_time = now or datetime.now(UTC)
    state_stamp = parse_datetime(state.updated_at)
    for position in state.positions:
        ticker = position.ticker
        observed = evidence_by_ticker.get(ticker, {})
        reasons: list[str] = []
        market = observed.get("market_state") or {}
        missing: list[str] = []
        if not position.thesis and position.thesis_status != "NOT_REQUIRED_DUST":
            missing.append("thesis_missing")
        elif position.thesis_status == "DRAFT":
            missing.append("thesis_draft_requires_validation")
        if state.ledger_history_complete is False:
            missing.append("ledger_history_incomplete")
        try:
            pit = PointInTime(parse_datetime(market.get("as_of")),
                              parse_datetime(market.get("available_at") or market.get("retrieved_at")), decision_time)
            market_eligible = (positive_number(market.get("current_price")) and pit.availability is Availability.ELIGIBLE and bool(market.get("source"))
                               and equity_observation_fresh(market.get("as_of"), decision_time,
                                                            daily=market.get("daily", True)))
        except ValueError:
            market_eligible = False
        if not positive_number(market.get("current_price")) or not market_eligible:
            missing.append("price_missing_stale_or_invalid")
        if observed.get("technical_condition") not in {"healthy", "weak", "breakdown"}:
            missing.append("technical_evidence_missing")
        if observed.get("invalidation") is True or position.candidate_status in {"invalidated", "broken"}:
            action = "EXIT_CANDIDATE"
            reasons.append("thesis_invalidated")
        elif observed.get("meaningful_new_information") is True:
            action = "REVIEW_REQUIRED"
            reasons.append("meaningful_new_information")
        elif missing:
            action = "REVIEW_REQUIRED"
            reasons.extend(missing)
        elif observed.get("technical_condition") == "weak":
            action = "MONITOR"
            reasons.append("price_below_20_session_average")
        elif observed.get("technical_condition") == "breakdown":
            action = "REDUCE_CANDIDATE"
            reasons.append("technical_weakness")
        else:
            action = "HOLD"
            reasons.append("thesis_and_current_evidence_have_no_recorded_break")
        decisions.append(
            {
                "ticker": ticker,
                "action": action,
                "thesis": position.thesis,
                "thesis_status": position.thesis_status,
                "quantity": position.quantity,
                "reasons": reasons,
                "evidence": dict(observed),
                "human_decision_required": True,
            }
        )
        evidence.append(
            Evidence(
                source="caller.portfolio.state",
                reference=f"portfolio-position-{ticker}",
                claim=f"Position state for {ticker} was supplied by the caller",
                kind=EvidenceKind.FACT,
                event_time=state_stamp,
                available_at=state_stamp,
                retrieved_at=decision_time,
                decision_time=decision_time,
                provenance=Provenance.CALLER_STATE,
                metadata={"updated_at": state.updated_at, "source_path": state.source_path},
            )
        )
        if market_eligible:
            market_stamp = parse_datetime(market.get("as_of"))
            evidence.append(
                Evidence(
                    source=str(market.get("source")),
                    reference=f"portfolio-market-{ticker}",
                    claim=f"{ticker} latest supported close {market.get('current_price')}",
                    kind=EvidenceKind.FACT,
                    event_time=market_stamp,
                    available_at=parse_datetime(market.get("available_at") or market.get("retrieved_at")),
                    retrieved_at=decision_time,
                    decision_time=decision_time,
                    provenance=Provenance.PROVIDER_RESULT,
                )
            )
    attention = [row for row in decisions if row["action"] != "HOLD"]
    extra = tuple(extra_warnings)
    if not state.positions:
        research = ResearchStatus.INSUFFICIENT_EVIDENCE
        operational = OperationalStatus.HEALTHY
        warnings = ("CALLER_STATE_MISSING: no positions in supplied portfolio state",) + extra
    elif attention:
        research = ResearchStatus.ACTION_REQUIRED
        operational = OperationalStatus.HEALTHY
        warnings = extra
    else:
        research = ResearchStatus.NO_SETUP
        operational = OperationalStatus.HEALTHY
        warnings = extra
    providers = [ProviderHealth(name="caller_state", status=OperationalStatus.HEALTHY, retrieved_at=decision_time)]
    market_providers = [ProviderHealth.from_dict(p) for row in evidence_by_ticker.values()
                        for p in row.get("provider_attempts", [])]
    providers.extend(market_providers)
    if market_providers and any(p.status is not OperationalStatus.HEALTHY for p in market_providers):
        operational = OperationalStatus.PARTIAL if any(p.status is OperationalStatus.HEALTHY for p in market_providers) else OperationalStatus.UNAVAILABLE
        if all(row["action"] == "REVIEW_REQUIRED" and "price_missing_stale_or_invalid" in row["reasons"] for row in decisions):
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
    if decisions and all(row["action"] == "REVIEW_REQUIRED" and
                         any(r in row["reasons"] for r in ("price_missing_stale_or_invalid", "technical_evidence_missing"))
                         for row in decisions):
        research = ResearchStatus.INSUFFICIENT_EVIDENCE
    if inventory_status is not None:
        providers.append(ProviderHealth(name="inventory", status=inventory_status, retrieved_at=decision_time))
        if inventory_status is OperationalStatus.UNAVAILABLE:
            operational = OperationalStatus.UNAVAILABLE
            if research in {ResearchStatus.NO_SETUP, ResearchStatus.SETUP_FOUND}:
                research = ResearchStatus.INSUFFICIENT_EVIDENCE
        elif inventory_status is OperationalStatus.PARTIAL and operational is OperationalStatus.HEALTHY:
            operational = OperationalStatus.PARTIAL
    return ResearchResult(
        workflow=WORKFLOW,
        status=research,
        operational=OperationalReport(
            status=operational,
            providers=tuple(providers),
        ),
        decision_time=decision_time,
        started_at=decision_time,
        completed_at=decision_time,
        mode=Mode.LIVE,
        payload={
            "positions": decisions,
            "read_only": True,
            "human_decision_required": True,
            "summary": {"attention": len(attention), "unchanged": len(decisions) - len(attention)},
            "execution_enabled": False,
            "pending_review": list(pending_review),
            "user_state": {
                "updated_at": state.updated_at,
                "source_path": state.source_path,
                "wallet_address": state.wallet_address,
            },
        },
        evidence=tuple(evidence),
        warnings=warnings,
        reasons=(ResearchReason(ReasonCode.CALLER_STATE_MISSING, ("caller portfolio positions",)),)
        if not state.positions else (ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE if operational is not OperationalStatus.HEALTHY else ReasonCode.REQUIRED_EVIDENCE_MISSING,
                                                   ("requested inventory refresh",) if inventory_status is OperationalStatus.UNAVAILABLE else ("current position market evidence",), True),)
        if research is ResearchStatus.INSUFFICIENT_EVIDENCE else (),
    )


class PortfolioWorkflow:
    name = WORKFLOW

    def __init__(self, *, store: ResearchStore | None = None, inventory=None, market_fetcher=None):
        self.store = store
        self.inventory = inventory
        self.market_fetcher = market_fetcher

    def run(
        self,
        state: PortfolioState,
        evidence_by_ticker: Mapping[str, Mapping[str, Any]] | None = None,
        *,
        now: datetime | None = None,
        refresh_inventory: bool = False,
    ) -> ResearchResult:
        inventory_status = None
        pending: tuple[Mapping[str, Any], ...] = ()
        extra_warnings: tuple[str, ...] = ()
        inventory_payload = None
        original_state = state
        if refresh_inventory:
            address = state.wallet_address or env("ROCKET_INVENTORY_ADDRESS")
            if self.inventory is None or not address:
                inventory_status = OperationalStatus.UNAVAILABLE
                extra_warnings = ("inventory refresh requested but no wallet address was available",)
            else:
                from rocket.providers.inventory import SolanaOndoInventory
                prior = self.store.load_state("wallet_inventory") if self.store else None
                previous = {r["mint"]: r for r in (prior or {}).get("records", [])} if (prior or {}).get("address") == address else {}
                for position in state.positions:
                    matches = [mint for mint, identity in self.inventory.registry.items() if identity.get("ticker") == position.ticker] if isinstance(self.inventory, SolanaOndoInventory) else []
                    mint = position.mint or (matches[0] if len(matches) == 1 else None)
                    if mint and mint not in previous:
                        previous[mint] = {"mint": mint, "ticker": position.ticker,
                                                   "quantity": position.quantity or 0}
                fetched = self.inventory.fetch(address=address, now=now, previous=previous) if isinstance(self.inventory, SolanaOndoInventory) else self.inventory.fetch(address=address, now=now)
                inventory_status = fetched.status
                inventory_payload = {"status": fetched.status.value, "failure_kind": fetched.failure_kind,
                                     "records": list(fetched.records), **dict(fetched.extras)}
                if fetched.status is OperationalStatus.HEALTHY:
                    by_ticker = {}
                    for position in state.positions:
                        matches = [r for r in fetched.records if
                                   (r.get("mint") == position.mint if position.mint else r.get("ticker") == position.ticker)
                                   and r.get("pending_review") is not True]
                        if len(matches) == 1:
                            by_ticker[position.ticker] = matches[0]
                    state = apply_inventory(state, by_ticker)
                    pending = tuple(
                        row
                        for row in fetched.records
                        if isinstance(row, Mapping) and row.get("pending_review") is True
                    )
                    if self.store:
                        self.store.save_state("wallet_inventory", {"address": address, "records": list(fetched.records),
                                                                   "retrieved_at": (now or datetime.now(UTC)).isoformat()})
                else:
                    extra_warnings = ("inventory provider did not return a healthy snapshot",)
        if evidence_by_ticker is None and state.positions:
            from rocket.providers.portfolio import acquire_position_evidence
            fetcher = self.market_fetcher or acquire_position_evidence
            evidence_by_ticker = fetcher([p.ticker for p in state.positions], now=now)
        if self.store and evidence_by_ticker:
            from rocket.candidates import candidate_id
            index = self.store.load_state("research_candidates") or {}
            enriched = {ticker: dict(row) for ticker, row in evidence_by_ticker.items()}
            for ticker, row in enriched.items():
                origin = index.get("candidates", {}).get(candidate_id(ticker), {}).get("origins", {}).get("disclosures", {})
                relevant = []
                for candidate in origin.get("inputs", [origin]):
                    trade = candidate.get("original_transaction", {})
                    try:
                        filed = datetime.fromisoformat(trade["disclosure_date"]).date()
                        if 0 <= ((now or datetime.now(UTC)).date() - filed).days <= 7:
                            relevant.append(trade)
                    except (ValueError, TypeError, KeyError):
                        continue
                row["disclosure_context"] = relevant
                if relevant:
                    row["meaningful_new_information"] = True
                    row["material_news_ids"] = [*row.get("material_news_ids", []), *[t["unique_id"] for t in relevant]]
            evidence_by_ticker = enriched
        result = review_positions(
            state,
            evidence_by_ticker,
            now=now,
            inventory_status=inventory_status,
            pending_review=pending,
            extra_warnings=extra_warnings,
        )
        previous_review = self.store.load_state("portfolio_review") if self.store else None
        prior_actions = (previous_review or {}).get("actions", {})
        missing_dimensions = {"price_missing_stale_or_invalid", "technical_evidence_missing",
                              "thesis_missing", "thesis_draft_requires_validation", "ledger_history_incomplete"}
        position_diagnostics = {row["ticker"]: [r for r in row["reasons"] if r in missing_dimensions]
                                for row in result.payload["positions"]
                                if any(r in missing_dimensions for r in row["reasons"])}
        transitions = []
        for row in result.payload["positions"]:
            old = prior_actions.get(row["ticker"])
            row["previous_action"] = old
            row["action_changed"] = old != row["action"]
            if (row["ticker"] not in position_diagnostics and row["action_changed"]
                    and (old is not None or row["action"] != "HOLD")):
                transitions.append({"ticker": row["ticker"], "from": old, "to": row["action"]})
        inventory_changes = [{"ticker": before.ticker, "expected_quantity": before.quantity,
                              "wallet_quantity": after.quantity, "thesis_preserved": True}
                             for before, after in zip(original_state.positions, state.positions, strict=True)
                             if before.quantity != after.quantity]
        inventory_failed = bool(refresh_inventory and inventory_status is not OperationalStatus.HEALTHY)
        diagnostic = inventory_failed or bool(position_diagnostics)
        import json

        from rocket.candidates import content_id
        news_id = content_id(json.dumps({ticker: row.get("material_news_ids", row.get("meaningful_new_information", False)) for ticker, row in (evidence_by_ticker or {}).items()}, sort_keys=True))
        material_news = any(r.get("meaningful_new_information") is True for r in (evidence_by_ticker or {}).values()) and news_id != (previous_review or {}).get("news_id")
        pending_ids = sorted(str(row.get("mint")) for row in pending)
        inventory_id = content_id(json.dumps(inventory_changes, sort_keys=True))
        new_pending = set(pending_ids) - set((previous_review or {}).get("pending_mints", []))
        changed_inventory = bool(inventory_changes) and inventory_id != (previous_review or {}).get("inventory_id")
        speak = bool(transitions or changed_inventory or new_pending or material_news)
        reasons = []
        for ticker, missing in position_diagnostics.items():
            attempts = (evidence_by_ticker or {}).get(ticker, {}).get("provider_attempts", [])
            failed_providers = [p["name"] for p in attempts
                                if p.get("status") in {"UNAVAILABLE", "ERROR"}]
            market_missing = [m for m in missing if m in {"price_missing_stale_or_invalid", "technical_evidence_missing"}]
            if failed_providers and market_missing:
                reasons.append(ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE,
                    tuple(f"{ticker}:{p}" for p in failed_providers), True))
            other_missing = [m for m in missing if not failed_providers or m not in market_missing]
            if other_missing:
                reasons.append(ResearchReason(ReasonCode.REQUIRED_EVIDENCE_MISSING,
                    tuple(f"{ticker}:{m}" for m in other_missing), bool(market_missing)))
        if inventory_failed:
            reasons.append(ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE,
                                          ("requested inventory reconciliation",), True))
        reasons = tuple(reasons) or result.reasons
        result = replace(result, payload={**result.payload, "transitions": transitions,
                                          "inventory": inventory_payload, "inventory_changes": inventory_changes,
                                          "position_diagnostics": position_diagnostics,
                                          "material_change": speak}, reasons=reasons,
                         presentation={"market_result": speak,
                                       "silent": not speak, "diagnostic_only": diagnostic and not speak})
        if self.store:
            self.store.save_result(result)
            if result.status is not ResearchStatus.INSUFFICIENT_EVIDENCE:
                self.store.save_state("portfolio_review", {"actions": {**prior_actions, **{r["ticker"]: r["action"] for r in result.payload["positions"] if r["ticker"] not in position_diagnostics}}, "news_id": news_id,
                                                          "pending_mints": pending_ids, "inventory_id": inventory_id})
        return result
