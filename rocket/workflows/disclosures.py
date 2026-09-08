"""Official vs secondary public filings. NO_NEW_RECORDS is not provider failure."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
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
from rocket.store import ResearchStore

WORKFLOW = "disclosures"


class SourceFamily(StrEnum):
    CONGRESS = "congress"
    EXECUTIVE = "executive"
    SECONDARY = "secondary"


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _stable_id(fields: Mapping[str, Any]) -> str:
    canonical = "|".join(str(fields.get(key) or "").strip().lower() for key in sorted(fields))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_record(record: Mapping[str, Any], *, family: SourceFamily) -> dict[str, Any] | None:
    subject = _clean(record.get("subject") or record.get("requested_subject") or record.get("name")) or "UNKNOWN"
    asset = _clean(record.get("asset") or record.get("symbol") or "FINANCIAL_DISCLOSURE_FILING")
    tx_type = _clean(record.get("transaction_type") or record.get("type") or "FILING")
    source = _clean(record.get("source_url") or record.get("link")) or "unlinked-official-record"
    fields = {
        "subject": subject,
        "asset": asset,
        "transaction_type": tx_type,
        "family": family.value,
        "source": source,
        "index_added_at": record.get("index_added_at"),
    }
    return {
        "subject_filer": subject,
        "owner": _clean(record.get("owner")),
        "asset": asset,
        "transaction_type": tx_type,
        "transaction_date": _clean(record.get("transaction_date")),
        "disclosure_date": _clean(record.get("disclosure_date")),
        "source_url_reference": source,
        "source_family": family.value,
        "provider": record.get("provider"),
        "index_added_at": record.get("index_added_at"),
        "unique_id": _stable_id({**fields, "provider": record.get("provider")}),
        "record_semantics": "SECONDARY_TRANSACTION_ROW"
        if family is SourceFamily.SECONDARY
        else "FILING_NOT_TRADE_ROW",
    }


class DisclosureWorkflow:
    name = WORKFLOW

    def __init__(self, *, store: ResearchStore | None = None):
        self.store = store or ResearchStore()

    def run(
        self,
        *,
        congress_records: Iterable[Mapping[str, Any]] = (),
        executive_records: Iterable[Mapping[str, Any]] = (),
        secondary_records: Iterable[Mapping[str, Any]] = (),
        now: datetime | None = None,
        provider_status: Mapping[str, Any] | None = None,
        warnings: Iterable[str] = (),
    ) -> ResearchResult:
        decided = now or datetime.now(UTC)
        unique: dict[str, dict[str, Any]] = {}
        for family, rows in (
            (SourceFamily.CONGRESS, congress_records),
            (SourceFamily.EXECUTIVE, executive_records),
            (SourceFamily.SECONDARY, secondary_records),
        ):
            for record in rows:
                normalized = normalize_record(record, family=family)
                if normalized:
                    unique.setdefault(normalized["unique_id"], normalized)
        seen_state = self.store.load_state("disclosures_seen") or {}
        seen = {str(item) for item in seen_state.get("unique_ids", [])}
        new_records = [record for record in unique.values() if record["unique_id"] not in seen]
        health = dict(provider_status or {})
        for family, info in health.items():
            if isinstance(info, dict) and info.get("status") != "UNAVAILABLE":
                info["research_result"] = (
                    "NEW_RECORDS"
                    if any(record["source_family"] == family for record in new_records)
                    else "NO_NEW_RECORDS"
                )
        failed = sum(1 for value in health.values() if isinstance(value, dict) and value.get("status") == "UNAVAILABLE")
        if health and failed == len(health):
            operational = OperationalStatus.UNAVAILABLE
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
            research_result = "PROVIDER_FAILURE"
        elif failed:
            operational = OperationalStatus.PARTIAL
            research = ResearchStatus.ACTION_REQUIRED if new_records else ResearchStatus.NO_SETUP
            research_result = "NEW_RECORDS" if new_records else "NO_NEW_RECORDS"
        else:
            operational = OperationalStatus.HEALTHY
            research = ResearchStatus.ACTION_REQUIRED if new_records else ResearchStatus.NO_SETUP
            research_result = "NEW_RECORDS" if new_records else "NO_NEW_RECORDS"
        evidence = [
            Evidence(
                source=record["source_family"],
                reference=f"disclosure-{record['unique_id']}",
                claim=f"Normalized public disclosure filing for {record['subject_filer']} / {record['asset']}",
                kind=EvidenceKind.FACT,
                event_time=decided,
                available_at=decided,
                retrieved_at=decided,
                decision_time=decided,
                provenance=Provenance.PROVIDER_RESULT,
                metadata={"source_family": record["source_family"], "provider": record.get("provider")},
            )
            for record in new_records
        ]
        providers = tuple(
            ProviderHealth(
                name=str(name),
                status=OperationalStatus.UNAVAILABLE
                if isinstance(info, dict) and info.get("status") == "UNAVAILABLE"
                else OperationalStatus.HEALTHY,
                retrieved_at=decided,
                failure_kind=info.get("failure_kind") if isinstance(info, dict) else None,
                coverage=info.get("research_result") if isinstance(info, dict) else None,
            )
            for name, info in health.items()
        ) or (
            ProviderHealth(name="disclosures", status=operational, retrieved_at=decided),
        )
        result = ResearchResult(
            workflow=WORKFLOW,
            status=research,
            operational=OperationalReport(status=operational, providers=providers),
            decision_time=decided,
            started_at=decided,
            completed_at=decided,
            mode=Mode.LIVE,
            payload={
                "records": new_records,
                "fetched_total": len(unique),
                "new_total": len(new_records),
                "record_semantics": "DISCLOSURE_RECORDS_NOT_STRATEGY_SIGNALS",
                "disclosure_is_not_a_buy_signal": True,
                "research_result": research_result,
                "provider_status": health,
                "execution_enabled": False,
            },
            evidence=tuple(evidence),
            reasons=(ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE,
                                    tuple(health), True),) if operational is OperationalStatus.UNAVAILABLE else (),
            warnings=(
                *warnings,
                *(
                    ("disclosures are delayed context and require independent portfolio evidence",)
                    if new_records
                    else ()
                ),
            ),
        )
        self.store.save_result(result)
        if research is ResearchStatus.INSUFFICIENT_EVIDENCE:
            return result
        self.store.save_state(
            "disclosures_seen",
            {"unique_ids": sorted(seen | set(unique)), "updated_at": decided.isoformat()},
        )
        return result
