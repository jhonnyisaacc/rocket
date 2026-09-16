"""Structured short catalysts. No event exists without evidence and PIT stamps."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from rocket.pit import parse_datetime

CATALYST_TYPES = (
    "EARNINGS_MISS",
    "GUIDANCE_CUT",
    "ESTIMATE_CUT",
    "EIGHT_K",
    "S1",
    "S3",
    "ATM",
    "SECONDARY_OFFERING",
    "DILUTION_OVERHANG",
    "LOCKUP_EXPIRATION",
    "INSIDER_SELLING",
    "ACTIVIST_SHORT_REPORT",
    "AUDITOR_ACCOUNTING",
    "MATERIAL_EVENT",
)

ITEM_TYPES = {
    "2.02": "EARNINGS_MISS",
    "2.05": "AUDITOR_ACCOUNTING",
    "2.06": "AUDITOR_ACCOUNTING",
    "1.01": "MATERIAL_EVENT",
    "1.02": "MATERIAL_EVENT",
    "7.01": "MATERIAL_EVENT",
    "8.01": "MATERIAL_EVENT",
}


def catalyst_record(
    *,
    type: str,
    event_time: datetime | str | None,
    available_at: datetime | str | None,
    source: str | None,
    summary: str | None,
    confidence: str | None = "LOW",
    extras: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    kind = str(type or "").strip().upper()
    if kind not in CATALYST_TYPES:
        return None
    try:
        event = parse_datetime(event_time)
        available = parse_datetime(available_at)
    except ValueError:
        return None
    if event is None or available is None or not str(source or "").strip() or not str(summary or "").strip():
        return None
    row = {
        "type": kind,
        "event_time": event.isoformat(),
        "available_at": available.isoformat(),
        "source": str(source).strip(),
        "summary": str(summary).strip(),
        "confidence": str(confidence or "LOW").strip().upper(),
    }
    if extras:
        row.update(dict(extras))
    return row


def eligible_catalysts(rows: Sequence[Mapping[str, Any]] | None, *, now: datetime) -> list[dict[str, Any]]:
    decided = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)
    eligible = []
    for row in rows or ():
        record = catalyst_record(
            type=str(row.get("type") or ""),
            event_time=row.get("event_time"),
            available_at=row.get("available_at"),
            source=row.get("source"),
            summary=row.get("summary"),
            confidence=row.get("confidence"),
            extras={k: v for k, v in row.items() if k not in {
                "type", "event_time", "available_at", "source", "summary", "confidence",
            }},
        )
        if record is None:
            continue
        available = parse_datetime(record["available_at"])
        event = parse_datetime(record["event_time"])
        if available is None or event is None or available > decided or event > decided:
            continue
        eligible.append(record)
    return eligible


def from_earnings_surprise(row: Mapping[str, Any], *, now: datetime) -> dict[str, Any] | None:
    actual, estimate = row.get("actualEarningResult"), row.get("estimatedEarning")
    try:
        actual_n, estimate_n = float(actual), float(estimate)
    except (TypeError, ValueError):
        return None
    if not (actual_n < estimate_n):
        return None
    stamp = row.get("date") or row.get("filingDate") or row.get("publishedDate")
    try:
        day = parse_datetime(stamp if "T" in str(stamp) else f"{stamp}T21:00:00+00:00")
    except ValueError:
        return None
    if day is None or day > now:
        return None
    return catalyst_record(
        type="EARNINGS_MISS",
        event_time=day,
        available_at=day,
        source=str(row.get("source") or "earnings-surprise"),
        summary=f"Reported EPS {actual_n} missed estimate {estimate_n}",
        confidence="MEDIUM",
        extras={"availability_basis": "report date treated as available_at; intraday publication time unknown"},
    )


def from_sec_filing(row: Mapping[str, Any], *, now: datetime) -> dict[str, Any] | None:
    form = str(row.get("form") or "").upper()
    filed = row.get("filingDate") or row.get("acceptanceDateTime") or row.get("filed")
    try:
        available = parse_datetime(filed if "T" in str(filed) else f"{filed}T21:00:00+00:00")
    except ValueError:
        return None
    if available is None or available > now:
        return None
    items = str(row.get("items") or "")
    accession = str(row.get("accessionNumber") or row.get("accn") or "").strip()
    source = str(row.get("source") or accession or "sec.submissions")
    if form in {"S-1", "S-1/A"}:
        kind, summary = "S1", f"{form} filed"
    elif form in {"S-3", "S-3/A"}:
        kind, summary = "S3", f"{form} filed"
    elif form in {"8-K", "8-K/A"}:
        kind = next((ITEM_TYPES[key] for key in ITEM_TYPES if key in items), "EIGHT_K")
        summary = f"{form} items {items}".strip() if items else f"{form} filed"
    else:
        return None
    return catalyst_record(
        type=kind,
        event_time=available,
        available_at=available,
        source=source,
        summary=summary,
        confidence="MEDIUM" if items else "LOW",
        extras={"form": form, "items": items or None, "accession": accession or None},
    )
