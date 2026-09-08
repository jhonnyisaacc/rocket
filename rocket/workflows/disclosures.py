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
from rocket.people import person_id
from rocket.store import ResearchStore

WORKFLOW = "disclosures"


class SourceFamily(StrEnum):
    CONGRESS = "congress"
    EXECUTIVE = "executive"
    SECONDARY = "secondary"
    INSIDER = "company_insider"
    CAMPAIGN = "campaign"
    OTHER = "other_official"


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
        "transaction_date": record.get("transaction_date"),
        "disclosure_date": record.get("disclosure_date"),
        "owner": record.get("owner"),
    }
    identity = ({"provider": record.get("provider"), "subject": person_id(subject) or subject,
                 "source_record_id": record["source_record_id"]}
                if record.get("source_record_id") else {**fields, "provider": record.get("provider")})
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
        "asset_type": record.get("asset_type"),
        "eligible_equity_context": record.get("eligible_equity_context", True),
        "description": record.get("description"),
        "amount_range": record.get("amount_range"),
        "source_record_id": record.get("source_record_id"),
        "underlying_source_family": record.get("underlying_source_family"),
        "verification_state": record.get("verification_state"),
        "resolution_tier": record.get("resolution_tier"),
        "resolved_ticker": record.get("resolved_ticker"),
        "disclosure_date_basis": record.get("disclosure_date_basis"),
        "document_sha256": record.get("document_sha256"),
        "person_id": person_id(subject),
        "identity_status": "EXACT_ALIAS" if person_id(subject) else "UNRESOLVED",
        "index_added_at": record.get("index_added_at"),
        "unique_id": _stable_id(identity),
        "record_semantics": record.get("record_semantics") or ("SECONDARY_TRANSACTION_ROW"
        if family is SourceFamily.SECONDARY
        else "FILING_NOT_TRADE_ROW"),
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
        subjects=None,
        historical_records: Iterable[Mapping[str, Any]] = (),
        context_fetcher=None,
        research_opportunities: bool = False,
        portfolio_tickers=None,
        watch_tickers=None,
        cross_system_coverage=None,
        historical_price_fetcher=None,
        history_acquisition=None,
    ) -> ResearchResult:
        decided = now or datetime.now(UTC)
        reference_coverage = cross_system_coverage or {
            "portfolio": "AVAILABLE" if portfolio_tickers is not None else "NOT_CONFIGURED",
            "watch": "AVAILABLE" if watch_tickers is not None else "NOT_CONFIGURED",
        }
        unknown_references = [name for name, rows in (("portfolio", portfolio_tickers), ("watch", watch_tickers))
                              if reference_coverage.get(name) != "AVAILABLE" or rows is None]
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
        from rocket.people import person_id
        selected_people = {person_id(s) or s for s in subjects} if subjects is not None else None
        if selected_people is not None:
            unique = {key: row for key, row in unique.items() if row["person_id"] in selected_people}
        seen_state = self.store.load_state("disclosures_seen") or {}
        seen = {str(item) for item in seen_state.get("unique_ids", [])}
        new_records = [record for record in unique.values() if record["unique_id"] not in seen]
        health = dict(provider_status or {})
        for family, info in health.items():
            if isinstance(info, dict) and info.get("status") != "UNAVAILABLE":
                info["research_result"] = (
                    "NEW_RECORDS"
                    if any(record["source_family"] == info.get("source_family", family.split(":")[0])
                           and (not info.get("record_provider") or record["provider"] == info["record_provider"])
                           for record in new_records)
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
        opportunities = []
        historical_scope = None
        if research_opportunities and research is not ResearchStatus.INSUFFICIENT_EVIDENCE:
            from rocket.candidates import evaluate_long, overlap, persist_candidates
            from rocket.providers.equity_research import acquire_equity_context
            history = dict(self.store.load_state("disclosure_history") or {})
            history.update(unique)
            for raw in historical_records:
                family = SourceFamily(raw.get("source_family", "secondary"))
                normalized = normalize_record(raw, family=family)
                if normalized and (selected_people is None or normalized["person_id"] in selected_people):
                    history[normalized["unique_id"]] = normalized
            trades = [r for r in history.values() if r["transaction_type"].lower() in {"purchase", "sale", "sale (full)", "sale (partial)"}
                      and r["asset"] not in {"UNKNOWN", "FINANCIAL_DISCLOSURE_FILING", "PUBLIC_FINANCIAL_DISCLOSURE"}
                      and (selected_people is None or r["person_id"] in selected_people)]
            # Bound fresh research to 30 distinct assets, newest disclosed first.
            trades.sort(key=lambda r: r.get("disclosure_date") or "", reverse=True)
            latest = {}
            for trade in trades:
                latest.setdefault((trade["person_id"], trade["asset"], trade["transaction_type"].lower().startswith("sale")), trade)
            historical_scope = {"transaction_records": len(trades), "distinct_person_asset_directions": len(latest),
                                "unknown_asset_examples_limit": 10, "listed_research_limit": 30}
            trades = list(latest.values())
            import re
            tickers = list(dict.fromkeys(r["asset"] for r in trades if r.get("eligible_equity_context") and re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", r["asset"])))[:30]
            contexts = (context_fetcher or acquire_equity_context)(tickers)
            from rocket.providers.historical_prices import price_history, transaction_context
            histories = {}
            for ticker in tickers:
                try:
                    histories[ticker] = (historical_price_fetcher or price_history)(ticker) if context_fetcher is None or historical_price_fetcher else {}
                except Exception:
                    histories[ticker] = {}
            decided = now or datetime.now(UTC)
            unknown_count = 0
            for trade in trades:
                if not trade.get("eligible_equity_context") or trade["asset"] not in tickers:
                    unknown_count += 1
                    if unknown_count > 10:
                        continue
                    opportunities.append({"ticker": None, "asset": trade["asset"], "direction": "unknown", "classification": "NEEDS_REVIEW",
                                          "original_transaction": trade, "reason": "Instrument identity or extracted transaction requires human review; not promoted to a listed-security candidate."})
                    continue
                ticker = trade["asset"]
                thesis = f"Historical {trade['subject_filer']} disclosure is context only; current company and price evidence must independently justify an opportunity."
                if trade["transaction_type"].lower().startswith("sale"):
                    candidate = {"ticker": ticker, "direction": "short", "classification": "SHORT_INPUT",
                                 "thesis": thesis, "requires_canonical_short_evaluation": True}
                else:
                    candidate = evaluate_long(ticker, contexts.get(ticker, {}), thesis=thesis,
                                               source_reference=trade["source_url_reference"], now=decided)
                tx_date, filing_date = trade.get("transaction_date"), trade.get("disclosure_date")
                try:
                    lag = (datetime.fromisoformat(filing_date) - datetime.fromisoformat(tx_date)).days
                    valid_dates = 0 <= lag and datetime.fromisoformat(filing_date).date() <= decided.date()
                except (ValueError, TypeError):
                    lag, valid_dates = None, False
                if not valid_dates:
                    candidate["classification"] = "NEEDS_REVIEW"
                    candidate["direction"] = "unknown"
                elif candidate["direction"] == "short" and (decided.date() - datetime.fromisoformat(tx_date).date()).days > 45:
                    candidate.update(classification="NOT_INTERESTING", direction="unknown",
                                     reason="Historical sale is too old to seed a new bearish evaluation by itself")
                candidate.update(original_transaction=trade, disclosure_lag_days=lag,
                                 overlap=overlap(self.store, ticker, portfolio=portfolio_tickers or (), watches=watch_tickers or ()),
                                 historical_price=None, move_since_transaction=None,
                                 historical_price_status="UNVERIFIED", opportunity_is_independent_of_person=True)
                candidate.update(transaction_context(histories.get(ticker, {}), tx_date, now=decided))
                candidate["already_considered"] = bool(candidate["overlap"])
                if set(candidate["overlap"]) & {"portfolio", "watch"}:
                    candidate["watch_proposal"] = None
                    candidate["disposition"] = "EXISTING_POSITION_OR_WATCH_CONTEXT"
                if unknown_references:
                    candidate.update(classification="NEEDS_REVIEW", direction="unknown", watch_proposal=None, entry=None,
                                     disposition="CALLER_REFERENCE_COVERAGE_UNKNOWN",
                                     missing_reference_coverage=unknown_references)
                candidate["overlap_coverage"] = reference_coverage
                average = contexts.get(ticker, {}).get("technical_basis", {}).get("average_20")
                price = candidate.get("current_price")
                if candidate["classification"] == "WATCH" and candidate.get("move_since_transaction", 0) is not None and candidate.get("move_since_transaction", 0) > .30 and average and price and price > average * 1.10:
                    candidate.update(classification="TOO_LATE", watch_proposal=None,
                                     timing_reason="Adjusted price advanced over 30% and is more than 10% above 20-session support; current entry is extended.")
                opportunities.append(candidate)
            self.store.save_state("disclosure_history", history)
            persist_candidates(self.store, "disclosures", [r for r in opportunities if r.get("ticker")], now=decided)
            if opportunities and research is not ResearchStatus.INSUFFICIENT_EVIDENCE:
                research = ResearchStatus.ACTION_REQUIRED
        import json

        from rocket.candidates import content_id
        material_id = content_id(json.dumps([(r.get("ticker"), r.get("asset"), r["classification"], r["original_transaction"]["unique_id"]) for r in opportunities], sort_keys=True))
        previous_material = self.store.load_state("disclosure_material") or {}
        material_change = bool(new_records) or bool(opportunities and material_id != previous_material.get("id"))
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
                "selected_people": sorted(selected_people) if selected_people is not None else None,
                "opportunities": opportunities,
                "historical_acquisition": history_acquisition,
                "historical_scope": historical_scope,
                "cross_system_coverage": reference_coverage,
                "material_change": material_change,
                "execution_enabled": False,
            },
            evidence=tuple(evidence),
            presentation={"market_result": material_change, "silent": not material_change,
                          "diagnostic_only": bool(failed and not material_change)},
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
        self.store.save_state("disclosure_material", {"id": material_id})
        return result
