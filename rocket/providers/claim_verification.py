"""Evidence-backed checks independent of speaker opinion and narrative synthesis."""

import math
from dataclasses import replace
from datetime import UTC, datetime

from rocket.claims import evaluate_claim, parse_claim
from rocket.models import Evidence, EvidenceKind, OperationalStatus, Provenance, ProviderHealth
from rocket.pit import parse_datetime
from rocket.providers.dispatch import failure_kind
from rocket.providers.indicators import fetch_indicator


def verify_claims(claims, decision_time, *, fetcher=None):
    from rocket.workflows.cava import CavaCorroboration
    checks, evidence, providers, acquired = [], [], [], {}
    fetcher = fetcher or fetch_indicator
    for claim in claims:
        check = parse_claim(claim.claim, claim_id=claim.reference, claim_date=claim.event_time.date())
        measure = check["exact_measure"]
        if measure and measure not in acquired:
            try:
                raw = fetcher(measure)
                available = parse_datetime(raw.get("retrieved_at"))
                if raw.get("measure") != measure or not raw.get("source") or not raw.get("citation") or available is None:
                    raise ValueError("exact measure or provenance missing")
                rows = raw["records"]
                if not rows or any(not math.isfinite(float(r["value"])) for r in rows):
                    raise ValueError("invalid observations")
                latest = max(datetime.fromisoformat(r["date"][:10]).replace(tzinfo=UTC) for r in rows)
                if latest > decision_time or (decision_time.date() - latest.date()).days > raw.get("max_age_days", 5):
                    raise ValueError("stale or future observations")
                acquired[measure] = raw
                evidence.append(Evidence(source=raw["source"], reference=f"exact-{measure}",
                                         claim=f"Current exact {measure} observations acquired", kind=EvidenceKind.FACT,
                                         event_time=latest, available_at=available, retrieved_at=available,
                                         decision_time=decision_time, provenance=Provenance.PROVIDER_RESULT,
                                         metadata={"measure": measure, "citation": raw["citation"], "unit": raw.get("unit"),
                                                   "observations": rows,
                                                   "components": raw.get("components"), "formula": raw.get("formula"),
                                                   "availability_basis": "current retrieved vintage, not historical availability"}))
                providers.append(ProviderHealth(f"indicator:{measure}", OperationalStatus.HEALTHY, available))
            except Exception as exc:
                acquired[measure] = None
                providers.append(ProviderHealth(f"indicator:{measure}", OperationalStatus.UNAVAILABLE,
                                               failure_kind=failure_kind(exc)))
        raw = acquired.get(measure)
        if raw:
            # Final decision clock is rechecked by the workflow after live reads.
            if not check.get("level_unit") or check["level_unit"] == raw.get("unit"):
                check = evaluate_claim(check, raw["records"])
            check["evidence"] = [f"exact-{measure}"]
            check["source"] = raw["source"]
            check["citation"] = raw["citation"]
            if check["kind"] == "FORECAST" and check["direction"]:
                current = evaluate_claim({**check, "kind": "CHANGE"}, raw["records"])
                check["current_evidence"] = {"VERIFIED": "supportive", "CONTRADICTED": "against"}.get(current["status"], "insufficient")
        checks.append(check)
    return CavaCorroboration(evidence=tuple(evidence), checks=tuple(checks), providers=tuple(providers),
                             contradictions=tuple(c for c in checks if c["status"] == "CONTRADICTED"))


def eligible_checks(corroboration, decided):
    evidence = tuple(replace(e, decision_time=decided) for e in corroboration.evidence)
    eligible = {e.reference for e in evidence if e.availability.value == "ELIGIBLE"
                and e.provenance is Provenance.PROVIDER_RESULT}
    checks = []
    for row in corroboration.checks:
        item = dict(row)
        if not set(item["evidence"]) <= eligible:
            item.update(status="FORECAST" if item["kind"] == "FORECAST" else "UNVERIFIED",
                        current_evidence="insufficient", interpretation="Evidence was unavailable at the decision time.")
        checks.append(item)
    return replace(corroboration, evidence=evidence, checks=tuple(checks),
                   contradictions=tuple(c for c in checks if c["status"] == "CONTRADICTED"))
