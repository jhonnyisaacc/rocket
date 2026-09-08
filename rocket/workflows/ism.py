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
    ReasonCode,
    ResearchReason,
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

    def __init__(self, *, store: ResearchStore | None = None, exposures=None, context_fetcher=None):
        self.store = store
        self.exposures = exposures
        self.context_fetcher = context_fetcher

    def run(
        self,
        *,
        now: datetime | None = None,
        reports: Mapping[str, ISMReport] | None = None,
        napm: Mapping[str, Any] | None = None,
        provider_failures: Mapping[str, str] | None = None,
        research_companies: bool = False,
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
                providers.append(ProviderHealth(name=f"ism.{kind}", status=OperationalStatus.UNAVAILABLE,
                                                retrieved_at=started, failure_kind=(provider_failures or {}).get(kind, "ReleaseUnavailable"),
                                                coverage="0 usable releases"))
                continue
            try:
                identity = release_identity(report, started)
                if report.kind != kind:
                    raise ValueError("report kind mismatch")
            except ValueError:
                warnings.append(f"{kind}: invalid release identity")
                payload_reports[kind] = {"status": "UNAVAILABLE", "headline_status": "INVALID_IDENTITY",
                                         "industry_rankings_status": "UNAVAILABLE"}
                providers.append(ProviderHealth(name=f"ism.{kind}", status=OperationalStatus.UNAVAILABLE,
                                                failure_kind="InvalidIdentity"))
                continue
            if identity["release_status"] != "CURRENT":
                warnings.append(f"{kind}: {identity['release_status']}")
                payload_reports[kind] = {"status": "UNAVAILABLE", "headline_status": identity["release_status"],
                                         "industry_rankings_status": "UNAVAILABLE", "identity": identity}
                providers.append(ProviderHealth(name=f"ism.{kind}", status=OperationalStatus.PARTIAL,
                                                failure_kind=identity["release_status"]))
                continue
            pmi, source = report.pmi, "ISM publisher release"
            if kind == "manufacturing" and pmi is None and isinstance(napm, Mapping):
                expected = identity["expected_reference_month"]
                # NAPM only for the matching reference month; never NMFBAI for services.
                if identity["reference_month"] == expected == napm.get("reference_month") and 0 < napm.get("value", 0) < 100:
                    pmi, source = napm["value"], "NAPM via FRED"
            row = _report_payload(report, pmi=pmi, pmi_source=source, identity=identity)
            payload_reports[kind] = row
            row["provider_failures"] = list(report.provider_failures)
            warnings.extend(f"{kind}:{failure}; independently acquired source retained: {report.source_url}" for failure in report.provider_failures)
            headline_ok = row["headline_status"] == "HEADLINE_VALID"
            providers.append(
                ProviderHealth(
                    name=f"ism.{kind}",
                    status=OperationalStatus.HEALTHY if row["status"] == "VALID" and not report.provider_failures else OperationalStatus.PARTIAL,
                    retrieved_at=started,
                    coverage=row["industry_rankings_status"],
                    failure_kind="PublisherFallback" if report.provider_failures else None,
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
            if row["industry_rankings_status"] == "INDUSTRY_RANKINGS_VALID":
                evidence.append(Evidence(source="ISM publisher release", reference=f"ism-{kind}-rankings",
                                         claim=f"{kind} industry rankings for {identity['reference_month']}",
                                         kind=EvidenceKind.FACT, event_time=started, available_at=started,
                                         retrieved_at=started, decision_time=started,
                                         provenance=Provenance.PROVIDER_RESULT,
                                         metadata={"identity": identity, "expanding": row["hottest_industries"],
                                                   "contracting": row["worst_industries"]}))
        live = [row for row in payload_reports.values() if "headline_status" in row]
        if live and all(row.get("status") == "VALID" and not row.get("provider_failures") for row in live):
            operational = OperationalStatus.HEALTHY
        elif any(row.get("headline_status") == "HEADLINE_VALID" or row.get("industry_rankings_status") == "INDUSTRY_RANKINGS_VALID" for row in live):
            operational = OperationalStatus.PARTIAL
        else:
            operational = OperationalStatus.UNAVAILABLE
        research = (
            ResearchStatus.INSUFFICIENT_EVIDENCE
            if operational is OperationalStatus.UNAVAILABLE
            else ResearchStatus.NO_SETUP
        )
        candidates, unmapped = [], []
        if research_companies:
            import json

            from rocket.candidates import evaluate_long, persist_candidates
            from rocket.config import DEFAULT_CONFIG_DIR
            from rocket.providers.equity_research import acquire_equity_context
            exposures = self.exposures if self.exposures is not None else json.loads((DEFAULT_CONFIG_DIR / "industry_exposure.json").read_text())
            seeds = []
            for kind, report in payload_reports.items():
                if report.get("industry_rankings_status") != "INDUSTRY_RANKINGS_VALID":
                    continue
                for direction, field in (("long", "hottest_industries"), ("short", "worst_industries")):
                    for industry in report[field]:
                        matched = exposures.get(industry["industry"], [])
                        if not matched:
                            unmapped.append({"industry": industry["industry"], "reason": "no reviewed company exposure mapping"})
                        for company in matched:
                            if company.get("source") and company.get("exposure"):
                                seeds.append({**company, "industry": industry["industry"], "report_type": kind,
                                              "direction": direction, "report_reference": f"ism-{kind}-rankings",
                                              "reference_month": report["identity"]["reference_month"]})
            contexts = (self.context_fetcher or acquire_equity_context)([r["ticker"] for r in seeds if r["direction"] == "long"])
            started = now or datetime.now(UTC)
            for seed in seeds:
                thesis = f"ISM {seed['reference_month']} {seed['report_type']}: {seed['industry']} is {'expanding' if seed['direction'] == 'long' else 'contracting'}. Company exposure: {seed['exposure']}."
                if seed["direction"] == "short":
                    candidate = {**seed, "classification": "SHORT_INPUT", "thesis": thesis,
                                 "requires_canonical_short_evaluation": True}
                else:
                    candidate = {**seed, **evaluate_long(seed["ticker"], contexts.get(seed["ticker"], {}),
                                                        thesis=thesis, source_reference=seed["source"], now=started)}
                candidates.append(candidate)
            if research is not ResearchStatus.INSUFFICIENT_EVIDENCE:
                persist_candidates(self.store, "ism", candidates, now=started)
            if any(r["classification"] in {"BUY_CANDIDATE", "WATCH"} for r in candidates):
                research = ResearchStatus.ACTION_REQUIRED
        missing_company = [r["ticker"] for r in candidates if r["classification"] == "NEEDS_REVIEW"]
        if missing_company and operational is OperationalStatus.HEALTHY:
            operational = OperationalStatus.PARTIAL
        from dataclasses import replace
        evidence = [replace(e, decision_time=started) for e in evidence]
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
                "candidates": candidates,
                "unmapped_industries": unmapped,
                "nmfbai_substituted_for_services_composite": False,
                "execution_enabled": False,
            },
            evidence=tuple(evidence),
            presentation={"market_result": research is ResearchStatus.ACTION_REQUIRED,
                          "silent": research is not ResearchStatus.ACTION_REQUIRED,
                          "diagnostic_only": bool(missing_company and research is not ResearchStatus.ACTION_REQUIRED)},
            warnings=tuple(warnings),
            reasons=(ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE
                                    if any(p.status is OperationalStatus.UNAVAILABLE for p in providers)
                                    else ReasonCode.REQUIRED_EVIDENCE_MISSING,
                                    tuple(f"{kind}:{row['headline_status']}" for kind, row in payload_reports.items()
                                          if row["headline_status"] != "HEADLINE_VALID"), True),)
            if research is ResearchStatus.INSUFFICIENT_EVIDENCE else (ResearchReason(ReasonCode.REQUIRED_EVIDENCE_MISSING,
                                                                                 tuple(f"{ticker}:current company research" for ticker in missing_company), True),) if missing_company else (),
        )
        if self.store:
            self.store.save_result(result)
        return result
