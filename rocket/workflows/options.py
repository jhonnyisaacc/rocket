"""Options research primitives. Never automatic VALIDATED. Crypto and stocks stay separate."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from rocket.models import (
    Evidence,
    EvidenceKind,
    Mode,
    OperationalReport,
    OperationalStatus,
    Provenance,
    ResearchResult,
    ResearchStatus,
)
from rocket.pit import Availability, PointInTime, parse_datetime
from rocket.store import ResearchStore

WORKFLOW = "options.scan"


class OptionDomain(StrEnum):
    CRYPTO = "crypto"
    STOCKS = "stocks"


def _number(value: object) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


class VolatilityInputs:
    def __init__(self, row: Mapping[str, Any], *, decision_time: datetime):
        self.underlying = str(row.get("underlying") or row.get("asset") or "").strip().upper()
        if not self.underlying:
            raise ValueError("underlying is required")
        self.event_time = parse_datetime(row.get("event_time"))
        self.available_at = parse_datetime(row.get("available_at"))
        self.decision_time = decision_time
        self.implied_volatility = _number(row.get("implied_volatility"))
        self.realized_volatility = _number(row.get("realized_volatility"))
        self.defined_risk = row.get("defined_risk") is True
        self.source = str(row.get("source") or "provided_snapshot")
        self.source_url = row.get("source_url")

    @property
    def point_in_time(self) -> PointInTime:
        return PointInTime(
            event_time=self.event_time,
            available_at=self.available_at,
            decision_time=self.decision_time,
        )

    def missing_dimensions(self) -> list[str]:
        missing = []
        if self.implied_volatility is None:
            missing.append("implied_volatility")
        if self.realized_volatility is None:
            missing.append("realized_volatility")
        if not self.defined_risk:
            missing.append("defined_risk")
        return missing

    def to_dict(self) -> dict[str, Any]:
        return {
            "underlying": self.underlying,
            "implied_volatility": self.implied_volatility,
            "realized_volatility": self.realized_volatility,
            "iv_rv_spread": (
                None
                if self.implied_volatility is None or self.realized_volatility is None
                else self.implied_volatility - self.realized_volatility
            ),
            "defined_risk": self.defined_risk,
            "source": self.source,
        }


def strategy_definition(domain: OptionDomain | str) -> dict[str, Any]:
    domain = OptionDomain(domain)
    if domain is OptionDomain.CRYPTO:
        return {
            "name": "crypto_iv_rv_defined_risk",
            "domain": domain.value,
            "underlyings": ["BTC", "ETH"],
            "state": "EXPERIMENTAL",
            "read_only": True,
        }
    return {
        "name": "stocks_volatility_catalyst_defined_risk",
        "domain": domain.value,
        "underlyings": ["EQUITY_UNIVERSE"],
        "state": "EXPERIMENTAL",
        "read_only": True,
    }


class OptionsWorkflow:
    name = WORKFLOW

    def __init__(self, *, store: ResearchStore | None = None):
        self.store = store

    def scan(
        self,
        domain: OptionDomain | str,
        rows: Sequence[Mapping[str, Any]],
        *,
        now: datetime | None = None,
    ) -> ResearchResult:
        definition = strategy_definition(domain)
        decided = now or datetime.now(UTC)
        normalized: list[VolatilityInputs] = []
        rejected: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            try:
                item = VolatilityInputs(row, decision_time=decided)
            except ValueError as exc:
                rejected.append({"row": index, "reason": "invalid_input", "detail": str(exc)})
                continue
            if item.point_in_time.availability is not Availability.ELIGIBLE:
                rejected.append(
                    {
                        "asset": item.underlying,
                        "reason": "availability_unknown"
                        if item.available_at is None
                        else "available_after_decision_time",
                    }
                )
                continue
            if definition["domain"] == "crypto" and item.underlying not in definition["underlyings"]:
                rejected.append({"asset": item.underlying, "reason": "outside_crypto_scope"})
                continue
            if item.event_time is None or decided - item.event_time > timedelta(days=1):
                rejected.append({"asset": item.underlying, "reason": "stale_volatility_snapshot"})
                continue
            missing = item.missing_dimensions()
            if missing:
                rejected.append({"asset": item.underlying, "reason": "missing_dimensions", "dimensions": missing})
                continue
            normalized.append(item)
        research = ResearchStatus.INSUFFICIENT_EVIDENCE
        warnings = (
            ("No point-in-time options snapshots were supplied; no recommendation was made.",)
            if not rows
            else ("No snapshot had sufficient point-in-time volatility and defined-risk inputs.",)
            if not normalized
            else ("The options strategy is not validated; observations are research-only.",)
        )
        evidence = tuple(
            Evidence(
                source=item.source,
                reference=f"option-input-{index + 1}",
                claim=f"{item.underlying} options snapshot supplied for research evaluation",
                kind=EvidenceKind.FACT,
                event_time=item.event_time,
                available_at=item.available_at,
                retrieved_at=decided,
                decision_time=decided,
                provenance=Provenance.TEST_FIXTURE if item.source == "fixture" else Provenance.PROVIDER_RESULT,
            )
            for index, item in enumerate(normalized)
        )
        result = ResearchResult(
            workflow=f"options.{definition['domain']}.scan",
            status=research,
            operational=OperationalReport(status=OperationalStatus.HEALTHY),
            decision_time=decided,
            started_at=decided,
            completed_at=decided,
            mode=Mode.REPLAY,
            payload={
                "strategy": definition,
                "strategy_state": "EXPERIMENTAL",
                "universe": definition["underlyings"],
                "eligible_inputs": len(normalized),
                "rejected_inputs": rejected,
                "observations": [item.to_dict() for item in normalized],
                "execution_enabled": False,
            },
            evidence=evidence,
            warnings=warnings,
        )
        if self.store:
            self.store.save_result(result)
        return result

    def evaluate(
        self,
        domain: OptionDomain | str,
        outcomes: Sequence[Mapping[str, Any]],
        *,
        now: datetime | None = None,
    ) -> ResearchResult:
        definition = strategy_definition(domain)
        decided = now or datetime.now(UTC)
        sample = [row for row in outcomes if _number(row.get("forward_return_pct", row.get("return_pct"))) is not None]
        result = ResearchResult(
            workflow=f"options.{definition['domain']}.evaluate",
            status=ResearchStatus.INSUFFICIENT_EVIDENCE,
            operational=OperationalReport(status=OperationalStatus.HEALTHY),
            decision_time=decided,
            started_at=decided,
            completed_at=decided,
            payload={
                "strategy": definition,
                "strategy_state": "EXPERIMENTAL",
                "metrics": {"sample_size": len(sample)},
                "cost_basis": "GROSS_UNCOSTED",
                "validation_gate": "No automatic VALIDATED state; require explicit human review.",
                "execution_enabled": False,
            },
            warnings=(
                "Evaluation is research-only; VALIDATED requires explicit human review.",
            ),
        )
        if self.store:
            self.store.save_result(result)
        return result
