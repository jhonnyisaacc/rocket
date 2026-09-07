"""ISM manufacturing and services scan. Headline and rankings stay separate."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
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
from rocket.providers.ism import ISMReport, expected_reference, release_identity
from rocket.store import ResearchStore

WORKFLOW = "ism"


def _report_payload(report: ISMReport, *, pmi: float | None, pmi_source: str, identity: Mapping[str, Any]) -> dict[str, Any]:
    headline_valid = pmi is not None and 0 < pmi < 100
    rankings_valid = bool(report.expanding or report.contracting)
    return {
        "kind": report.kind,
        "report_month": report.report_month,
        "pmi": pmi,
        "pmi_source": pmi_source,
        "headline_status": "HEADLINE_VALID" if headline_valid else "UNAVAILABLE",
        "industry_rankings_status": "INDUSTRY_RANKINGS_VALID" if rankings_valid else "UNAVAILABLE",
        "hottest_industries": [item.__dict__ for item in report.expanding],
        "worst_industries": [item.__dict__ for item in report.contracting],
        "identity": dict(identity),
        "status": "VALID"
        if headline_valid and rankings_valid
        else "PARTIAL"
        if headline_valid or rankings_valid
        else "UNAVAILABLE",
        "source_url": report.source_url,
    }


class IsmWorkflow:
    name = WORKFLOW

    def __init__(self, *, store: ResearchStore | None = None):
        self.store = store

    def run(
        self,
        *,
        now: datetime | None = None,
        reports: Mapping[str, ISMReport] | None = None,
        napm: float | None = None,
    ) -> ResearchResult:
        started = now or datetime.now(UTC)
        warnings: list[str] = []
        providers: list[ProviderHealth] = []
        evidence: list[Evidence] = []
        payload_reports: dict[str, Any] = {}
        for kind in ("manufacturing", "services"):
            report = (reports or {}).get(kind)
            if report is None:
                warnings.append(f"{kind} release unavailable")
                identity = {
                    "report_type": kind.upper(),
                    "reference_month": expected_reference(kind, started).strftime("%Y-%m"),
                    "release_status": "UNAVAILABLE",
                }
                payload_reports[kind] = {
                    "headline_status": "UNAVAILABLE",
                    "industry_rankings_status": "UNAVAILABLE",
                    "identity": identity,
                    "status": "UNAVAILABLE",
                }
                providers.append(ProviderHealth(name=f"ism.{kind}", status=OperationalStatus.UNAVAILABLE))
                continue
            identity = release_identity(report, started)
            pmi, source = report.pmi, "ISM publisher release"
            if kind == "manufacturing" and napm is not None and 0 < napm < 100:
                expected = identity["expected_reference_month"]
                # NAPM only for the matching reference month; never NMFBAI for services.
                if identity["reference_month"] == expected:
                    pmi, source = napm, "NAPM via FRED"
            row = _report_payload(report, pmi=pmi, pmi_source=source, identity=identity)
            payload_reports[kind] = row
            headline_ok = row["headline_status"] == "HEADLINE_VALID"
            providers.append(
                ProviderHealth(
                    name=f"ism.{kind}",
                    status=OperationalStatus.HEALTHY if headline_ok else OperationalStatus.PARTIAL,
                    retrieved_at=started,
                    coverage=row["industry_rankings_status"],
                )
            )
            if headline_ok:
                evidence.append(
                    Evidence(
                        source=source,
                        reference=f"ism-{kind}-headline",
                        claim=f"{kind} PMI {pmi} for {identity['reference_month']}",
                        kind=EvidenceKind.FACT,
                        event_time=started,
                        available_at=started,
                        retrieved_at=started,
                        decision_time=started,
                        provenance=Provenance.PROVIDER_RESULT,
                        metadata={"identity": identity},
                    )
                )
        live = [row for row in payload_reports.values() if "headline_status" in row]
        if live and all(row.get("headline_status") == "HEADLINE_VALID" for row in live):
            operational = OperationalStatus.HEALTHY
        elif any(row.get("headline_status") == "HEADLINE_VALID" for row in live):
            operational = OperationalStatus.PARTIAL
        else:
            operational = OperationalStatus.UNAVAILABLE
        research = (
            ResearchStatus.INSUFFICIENT_EVIDENCE
            if operational is OperationalStatus.UNAVAILABLE
            else ResearchStatus.NO_SETUP
        )
        result = ResearchResult(
            workflow=WORKFLOW,
            status=research,
            operational=OperationalReport(status=operational, providers=tuple(providers)),
            decision_time=started,
            started_at=started,
            completed_at=started,
            mode=Mode.LIVE,
            payload={
                "reports": payload_reports,
                "nmfbai_substituted_for_services_composite": False,
                "execution_enabled": False,
            },
            evidence=tuple(evidence),
            warnings=tuple(warnings),
        )
        if self.store:
            self.store.save_result(result)
        return result
