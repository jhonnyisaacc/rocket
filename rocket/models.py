"""One result type. Operational status is separate from research status."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

import orjson

from rocket.pit import Availability, PointInTime, iso, parse_datetime


class ResearchStatus(StrEnum):
    SETUP_FOUND = "SETUP_FOUND"
    NO_SETUP = "NO_SETUP"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    ERROR = "ERROR"


class ReasonCode(StrEnum):
    CALLER_STATE_MISSING = "CALLER_STATE_MISSING"
    INVALID_INPUT = "INVALID_INPUT"
    REQUIRED_PROVIDER_UNAVAILABLE = "REQUIRED_PROVIDER_UNAVAILABLE"
    REQUIRED_EVIDENCE_MISSING = "REQUIRED_EVIDENCE_MISSING"
    CORROBORATION_INSUFFICIENT = "CORROBORATION_INSUFFICIENT"
    STRATEGY_UNVALIDATED = "STRATEGY_UNVALIDATED"
    WARMUP_STATE = "WARMUP_STATE"
    LEGACY_UNCLASSIFIED = "LEGACY_UNCLASSIFIED"


@dataclass(frozen=True)
class ResearchReason:
    code: ReasonCode
    missing: tuple[str, ...]
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "missing": list(self.missing), "retryable": self.retryable}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ResearchReason:
        return cls(ReasonCode(value["code"]), tuple(value["missing"]), bool(value.get("retryable")))


class OperationalStatus(StrEnum):
    HEALTHY = "HEALTHY"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class EvidenceKind(StrEnum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


class Mode(StrEnum):
    LIVE = "LIVE"
    REPLAY = "REPLAY"


class SafetyBoundary(StrEnum):
    READ_ONLY_RESEARCH_ONLY_HUMAN_GATED = "READ_ONLY_RESEARCH_ONLY_HUMAN_GATED"


class Provenance(StrEnum):
    UNKNOWN = "UNKNOWN"
    PROVIDER_RESULT = "PROVIDER_RESULT"
    USER_STATE = "USER_STATE"
    DOMAIN_RULE = "DOMAIN_RULE"
    TEST_FIXTURE = "TEST_FIXTURE"
    CALLER_STATE = "CALLER_STATE"


@dataclass(frozen=True)
class ProviderHealth:
    name: str
    status: OperationalStatus
    retrieved_at: datetime | None = None
    failure_kind: str | None = None
    coverage: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "retrieved_at": iso(self.retrieved_at),
            "failure_kind": self.failure_kind,
            "coverage": self.coverage,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ProviderHealth:
        return cls(
            name=str(value.get("name") or ""),
            status=OperationalStatus(str(value.get("status") or OperationalStatus.ERROR)),
            retrieved_at=parse_datetime(value.get("retrieved_at")),
            failure_kind=value.get("failure_kind"),
            coverage=value.get("coverage"),
        )


@dataclass(frozen=True)
class OperationalReport:
    status: OperationalStatus
    providers: tuple[ProviderHealth, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "providers": [item.to_dict() for item in self.providers],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> OperationalReport:
        value = value or {}
        raw = value.get("providers") or []
        return cls(
            status=OperationalStatus(str(value.get("status") or OperationalStatus.ERROR)),
            providers=tuple(ProviderHealth.from_dict(item) for item in raw),
        )


@dataclass(frozen=True)
class Evidence:
    source: str
    reference: str
    claim: str
    kind: EvidenceKind = EvidenceKind.UNKNOWN
    event_time: datetime | None = None
    observed_at: datetime | None = None
    available_at: datetime | None = None
    retrieved_at: datetime | None = None
    decision_time: datetime | None = None
    provenance: Provenance = Provenance.UNKNOWN
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.reference.strip() or not self.claim.strip():
            raise ValueError("evidence source, reference, and claim are required")
        self.point_in_time.validate()

    @property
    def point_in_time(self) -> PointInTime:
        return PointInTime(
            event_time=self.event_time,
            available_at=self.available_at,
            decision_time=self.decision_time,
        )

    @property
    def availability(self) -> Availability:
        return self.point_in_time.availability

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "reference": self.reference,
            "claim": self.claim,
            "kind": self.kind.value,
            "event_time": iso(self.event_time),
            "observed_at": iso(self.observed_at),
            "available_at": iso(self.available_at),
            "retrieved_at": iso(self.retrieved_at),
            "decision_time": iso(self.decision_time),
            "availability": self.availability.value,
            "provenance": self.provenance.value,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Evidence:
        pit = PointInTime.from_dict(value.get("point_in_time") or value)
        return cls(
            source=str(value.get("source") or ""),
            reference=str(value.get("reference") or value.get("citation") or value.get("reference_id") or ""),
            claim=str(value.get("claim") or ""),
            kind=EvidenceKind(str(value.get("kind") or EvidenceKind.UNKNOWN.value)),
            event_time=pit.event_time,
            observed_at=parse_datetime(value.get("observed_at")),
            available_at=pit.available_at,
            retrieved_at=parse_datetime(value.get("retrieved_at")),
            decision_time=pit.decision_time,
            provenance=Provenance(str(value.get("provenance") or Provenance.UNKNOWN.value)),
            metadata=value.get("metadata") or {},
        )


def _dumps(payload: Mapping[str, Any]) -> None:
    orjson.dumps(dict(payload), option=orjson.OPT_STRICT_INTEGER)


@dataclass(frozen=True)
class ResearchResult:
    """Structured output consumed by any bot runtime. Never an execution instruction."""

    workflow: str
    status: ResearchStatus
    operational: OperationalReport
    decision_time: datetime
    started_at: datetime
    run_id: str = field(default_factory=lambda: uuid4().hex)
    completed_at: datetime | None = None
    mode: Mode = Mode.LIVE
    payload: Mapping[str, Any] = field(default_factory=dict)
    evidence: tuple[Evidence, ...] = ()
    warnings: tuple[str, ...] = ()
    reasons: tuple[ResearchReason, ...] = ()
    safety_boundary: SafetyBoundary = SafetyBoundary.READ_ONLY_RESEARCH_ONLY_HUMAN_GATED
    presentation: Mapping[str, bool] | None = None

    def validate(self) -> None:
        if not self.workflow.strip():
            raise ValueError("workflow is required")
        if self.decision_time.tzinfo is None or self.started_at.tzinfo is None:
            raise ValueError("decision_time and started_at must include a timezone")
        if self.completed_at is not None and self.completed_at.tzinfo is None:
            raise ValueError("completed_at must include a timezone")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload must be a mapping")
        if self.payload.get("execution_enabled") is True:
            raise ValueError("execution_enabled must be false")
        if self.status is ResearchStatus.INSUFFICIENT_EVIDENCE and not self.reasons:
            raise ValueError("INSUFFICIENT_EVIDENCE requires machine-readable reasons")
        if any(not reason.missing or not all(reason.missing) for reason in self.reasons):
            raise ValueError("research reasons require explicit missing dimensions")
        if self.status is ResearchStatus.INSUFFICIENT_EVIDENCE and self.payload.get("cursor_advanced"):
            raise ValueError("INSUFFICIENT_EVIDENCE cannot advance a research cursor")
        if self.operational.status is OperationalStatus.HEALTHY and self.payload.get("coverage_status") == "DATA_UNAVAILABLE":
            raise ValueError("HEALTHY cannot claim DATA_UNAVAILABLE coverage")
        if self.status is ResearchStatus.ERROR and not self.warnings:
            raise ValueError("ERROR requires a visible warning")
        if self.operational.status is OperationalStatus.UNAVAILABLE and self.status in {
            ResearchStatus.NO_SETUP,
            ResearchStatus.SETUP_FOUND,
        }:
            raise ValueError("UNAVAILABLE operational status cannot pair with NO_SETUP or SETUP_FOUND")
        if self.status is ResearchStatus.SETUP_FOUND and not any(
            item.availability is Availability.ELIGIBLE
            and item.decision_time == self.decision_time
            for item in self.evidence
        ):
            raise ValueError("SETUP_FOUND requires at least one evidence reference eligible at result decision_time")
        if self.mode is Mode.REPLAY:
            if self.payload.get("loaded_live_context") is True:
                raise ValueError("REPLAY must never load live context")
        _dumps(dict(self.payload))
        for item in self.evidence:
            _dumps(dict(item.metadata))
            item.point_in_time.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": 2,
            "run_id": self.run_id,
            "workflow": self.workflow,
            "mode": self.mode.value,
            "operational": self.operational.to_dict(),
            "status": self.status.value,
            "decision_time": iso(self.decision_time),
            "started_at": iso(self.started_at),
            "completed_at": iso(self.completed_at),
            "evidence": [item.to_dict() for item in self.evidence],
            "warnings": list(self.warnings),
            "reasons": [reason.to_dict() for reason in self.reasons],
            "presentation": self.presentation_metadata(),
            "payload": dict(self.payload),
            "safety_boundary": self.safety_boundary.value,
        }

    def presentation_metadata(self) -> dict[str, bool]:
        diagnostic = self.status in {ResearchStatus.INSUFFICIENT_EVIDENCE, ResearchStatus.ERROR}
        if diagnostic:
            return {"market_result": False, "silent": True, "diagnostic_only": True}
        market = self.status in {ResearchStatus.SETUP_FOUND, ResearchStatus.ACTION_REQUIRED} or self.workflow in {"macro", "ism"}
        result = dict(self.presentation) if self.presentation is not None else {
            "market_result": market, "silent": not market, "diagnostic_only": False}
        # Partial research can coexist with operator diagnostics. Never hide typed errors.
        if any(r.code in {ReasonCode.INVALID_INPUT, ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE}
               for r in self.reasons):
            result["diagnostic_only"] = not result["market_result"]
            result["silent"] = not result["market_result"]
        return result

    def to_json(self) -> bytes:
        return orjson.dumps(self.to_dict(), option=orjson.OPT_INDENT_2)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ResearchResult:
        decision_time = parse_datetime(value.get("decision_time"))
        started_at = parse_datetime(value.get("started_at"))
        if decision_time is None or started_at is None:
            raise ValueError("decision_time and started_at are required")
        reasons = tuple(ResearchReason.from_dict(item) for item in value.get("reasons") or [])
        if value.get("schema_version", 1) == 1 and value.get("status") == ResearchStatus.INSUFFICIENT_EVIDENCE and not reasons:
            reasons = (ResearchReason(ReasonCode.LEGACY_UNCLASSIFIED,
                                      ("legacy run did not record missing dimensions; rerun for classification",)),)
        result = cls(
            workflow=str(value.get("workflow") or ""),
            status=ResearchStatus(str(value.get("status") or "")),
            operational=OperationalReport.from_dict(value.get("operational")),
            decision_time=decision_time,
            started_at=started_at,
            run_id=str(value.get("run_id") or uuid4().hex),
            completed_at=parse_datetime(value.get("completed_at")),
            mode=Mode(str(value.get("mode") or Mode.LIVE.value)),
            payload=value.get("payload") or {},
            evidence=tuple(Evidence.from_dict(item) for item in value.get("evidence") or []),
            warnings=tuple(str(item) for item in value.get("warnings") or []),
            reasons=reasons,
            presentation=value.get("presentation"),
            safety_boundary=SafetyBoundary(
                str(value.get("safety_boundary") or SafetyBoundary.READ_ONLY_RESEARCH_ONLY_HUMAN_GATED)
            ),
        )
        result.validate()
        return result

    def to_markdown(self) -> str:
        self.validate()
        lines = [
            f"# {self.workflow}",
            "",
            f"- Research: **{self.status.value}**",
            f"- Operational: **{self.operational.status.value}**",
            f"- Mode: `{self.mode.value}`",
            f"- Run: `{self.run_id}`",
            f"- Decision time: `{iso(self.decision_time)}`",
            f"- Safety: `{self.safety_boundary.value}`",
            "",
            "## Result",
            "",
        ]
        if self.payload:
            for key, value in self.payload.items():
                lines.append(f"- **{key}:** {value}")
        else:
            lines.append("_No structured payload._")
        lines.extend(["", "## Evidence", ""])
        if self.evidence:
            for item in self.evidence:
                lines.append(
                    f"- `{item.kind.value}` `{item.reference}` ({item.availability.value}): "
                    f"{item.claim} [{item.source}]"
                )
        else:
            lines.append("_No evidence references._")
        if self.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines) + "\n"


def exit_code(result: ResearchResult) -> int:
    """Bots must treat healthy NO_SETUP as success."""
    if result.status is ResearchStatus.ERROR or result.operational.status is OperationalStatus.ERROR:
        return 1
    if result.operational.status is OperationalStatus.UNAVAILABLE:
        return 2
    return 0
