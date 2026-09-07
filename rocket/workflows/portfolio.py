"""Per-position review. Caller owns theses; wallet inventory is read-only evidence."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
    ResearchResult,
    ResearchStatus,
)
from rocket.pit import parse_datetime
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
    positions = tuple(
        PositionState(
            ticker=str(item.get("ticker") or "").upper(),
            thesis=str(item.get("thesis") or ""),
            thesis_status=str(item.get("thesis_status") or "RECORDED"),
            thesis_reference=item.get("thesis_reference"),
            source_strategy=str(item.get("source_strategy") or "manual"),
            candidate_status=str(item.get("candidate_status") or "current"),
            watch_target=item.get("watch_target"),
            quantity=item.get("quantity") if item.get("quantity") is not None else item.get("shares"),
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
        if isinstance(row, Mapping) and positive_number(row.get("quantity")):
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
        if not positive_number(market.get("current_price")) or not equity_observation_fresh(
            market.get("as_of"), decision_time
        ):
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
        elif observed.get("technical_condition") in {"weak", "breakdown"}:
            action = "REDUCE_CANDIDATE"
            reasons.append("technical_weakness")
        elif observed.get("macro_regime") in {None, "unknown", "UNKNOWN"}:
            action = "REVIEW_REQUIRED"
            reasons.append("macro_context_missing")
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
        if market.get("as_of") and market.get("source"):
            market_stamp = parse_datetime(market.get("as_of"))
            evidence.append(
                Evidence(
                    source=str(market.get("source")),
                    reference=f"portfolio-market-{ticker}",
                    claim=f"{ticker} latest supported close {market.get('current_price')}",
                    kind=EvidenceKind.FACT,
                    event_time=market_stamp,
                    available_at=parse_datetime(market.get("retrieved_at")) or market_stamp,
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
    )


class PortfolioWorkflow:
    name = WORKFLOW

    def __init__(self, *, store: ResearchStore | None = None, inventory=None):
        self.store = store
        self.inventory = inventory

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
        if refresh_inventory:
            address = state.wallet_address or env("ROCKET_INVENTORY_ADDRESS")
            if self.inventory is None or not address:
                inventory_status = OperationalStatus.UNAVAILABLE
                extra_warnings = ("inventory refresh requested but no wallet address was available",)
            else:
                fetched = self.inventory.fetch(address=address, now=now)
                inventory_status = fetched.status
                if fetched.status is OperationalStatus.HEALTHY:
                    by_ticker = {
                        str(row.get("ticker") or "").upper(): row
                        for row in fetched.records
                        if isinstance(row, Mapping) and row.get("ticker") and row.get("ticker") != "UNKNOWN"
                    }
                    state = apply_inventory(state, by_ticker)
                    pending = tuple(
                        row
                        for row in fetched.records
                        if isinstance(row, Mapping) and row.get("pending_review") is True
                    )
                else:
                    extra_warnings = ("inventory provider did not return a healthy snapshot",)
        result = review_positions(
            state,
            evidence_by_ticker,
            now=now,
            inventory_status=inventory_status,
            pending_review=pending,
            extra_warnings=extra_warnings,
        )
        if self.store:
            self.store.save_result(result)
        return result
