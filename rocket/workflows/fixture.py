"""In-repo fixture workflow so the harness exists before live providers."""

from __future__ import annotations

from datetime import datetime

from rocket.models import (
    Evidence,
    EvidenceKind,
    Mode,
    OperationalReport,
    OperationalStatus,
    Provenance,
    ReasonCode,
    ResearchReason,
    ResearchResult,
    ResearchStatus,
)
from rocket.pit import PointInTime


class FixtureWorkflow:
    name = "fixture.scan"

    def scan(
        self,
        *,
        decision_time: datetime,
        available_at: datetime | None,
        operational: OperationalStatus = OperationalStatus.HEALTHY,
        research: ResearchStatus = ResearchStatus.NO_SETUP,
        claim: str = "fixture observation",
        mode: Mode = Mode.LIVE,
        warnings: tuple[str, ...] = (),
        loaded_live_context: bool = False,
    ) -> ResearchResult:
        evidence = ()
        if available_at is not None or research is ResearchStatus.SETUP_FOUND:
            pit = PointInTime(
                event_time=available_at or decision_time,
                available_at=available_at,
                decision_time=decision_time,
            )
            evidence = (
                Evidence(
                    source="fixture",
                    reference="fixture-1",
                    claim=claim,
                    kind=EvidenceKind.FACT,
                    event_time=pit.event_time,
                    available_at=pit.available_at,
                    decision_time=decision_time,
                    provenance=Provenance.TEST_FIXTURE,
                ),
            )
        if research is ResearchStatus.ERROR and not warnings:
            warnings = ("fixture error",)
        return ResearchResult(
            workflow=self.name,
            status=research,
            operational=OperationalReport(status=operational),
            decision_time=decision_time,
            started_at=decision_time,
            completed_at=decision_time,
            mode=mode,
            payload={
                "execution_enabled": False,
                "loaded_live_context": loaded_live_context,
            },
            evidence=evidence,
            warnings=warnings,
            reasons=(ResearchReason(ReasonCode.REQUIRED_EVIDENCE_MISSING, ("fixture observation",)),) if research is ResearchStatus.INSUFFICIENT_EVIDENCE else (),
        )
