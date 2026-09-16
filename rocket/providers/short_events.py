"""Structured short catalysts. No event exists without evidence and PIT stamps."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from rocket.pit import parse_datetime

CATALYST_TYPES = (
    "EARNINGS_MISS",
    "EARNINGS_EVENT",
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
    "AUDITOR_CHANGE",
    "AUDITOR_ACCOUNTING",
    "NON_RELIANCE",
    "MATERIAL_IMPAIRMENT",
    "EXIT_OR_DISPOSAL_COST",
    "MANAGEMENT_CHANGE",
    "OTHER_EVENT",
    "MATERIAL_EVENT",
)
DIRECTIONS = ("BEARISH", "BULLISH", "NEUTRAL", "UNKNOWN")

# Official SEC 8-K item titles. Direction is BEARISH only when the item itself
# is a structured downside event, not merely a filing.
ITEM_SEMANTICS = {
    "2.02": {
        "type": "EARNINGS_EVENT",
        "direction": "UNKNOWN",
        "title": "Results of Operations and Financial Condition",
        "bearish_by_itself": False,
    },
    "2.05": {
        "type": "EXIT_OR_DISPOSAL_COST",
        "direction": "UNKNOWN",
        "title": "Costs Associated with Exit or Disposal Activities",
        "bearish_by_itself": False,
    },
    "2.06": {
        "type": "MATERIAL_IMPAIRMENT",
        "direction": "BEARISH",
        "title": "Material Impairments",
        "bearish_by_itself": True,
    },
    "4.01": {
        "type": "AUDITOR_CHANGE",
        "direction": "UNKNOWN",
        "title": "Changes in Registrant's Certifying Accountant",
        "bearish_by_itself": False,
    },
    "4.02": {
        "type": "NON_RELIANCE",
        "direction": "BEARISH",
        "title": "Non-Reliance on Previously Issued Financial Statements or a Related Audit Report or Completed Interim Review",
        "bearish_by_itself": True,
    },
    "5.02": {
        "type": "MANAGEMENT_CHANGE",
        "direction": "UNKNOWN",
        "title": "Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers",
        "bearish_by_itself": False,
    },
    "8.01": {
        "type": "OTHER_EVENT",
        "direction": "UNKNOWN",
        "title": "Other Events",
        "bearish_by_itself": False,
    },
}

DIRECTIONAL_TYPES = {
    "EARNINGS_MISS": "BEARISH",
    "GUIDANCE_CUT": "BEARISH",
    "ESTIMATE_CUT": "BEARISH",
    "MATERIAL_IMPAIRMENT": "BEARISH",
    "NON_RELIANCE": "BEARISH",
    "ACTIVIST_SHORT_REPORT": "BEARISH",
}


def parse_sec_items(raw: Any) -> list[str]:
    text = str(raw or "")
    found: list[str] = []
    for token in text.replace(";", ",").split(","):
        item = token.strip()
        if not item:
            continue
        if item.lower().startswith("item "):
            item = item[5:].strip()
        found.append(item)
    return found


def item_semantics(item: str) -> dict[str, Any] | None:
    key = str(item or "").strip()
    return ITEM_SEMANTICS.get(key)


def _normalize_direction(value: Any, *, type: str) -> str:
    raw = str(value or "").strip().upper()
    if raw in DIRECTIONS:
        return raw
    return DIRECTIONAL_TYPES.get(type, "UNKNOWN")


def catalyst_record(
    *,
    type: str,
    event_time: datetime | str | None,
    available_at: datetime | str | None,
    source: str | None,
    summary: str | None,
    confidence: str | None = "LOW",
    direction: str | None = None,
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
        "direction": _normalize_direction(direction, type=kind),
        "event_time": event.isoformat(),
        "available_at": available.isoformat(),
        "source": str(source).strip(),
        "summary": str(summary).strip(),
        "confidence": str(confidence or "LOW").strip().upper(),
        "counts_for_selection": False,
    }
    if extras:
        row.update({k: v for k, v in dict(extras).items() if k not in row})
    row["counts_for_selection"] = row["direction"] == "BEARISH"
    return row


def eligible_catalysts(rows: Sequence[Mapping[str, Any]] | None, *, now: datetime) -> list[dict[str, Any]]:
    decided = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)
    eligible = []
    for row in rows or ():
        if not isinstance(row, Mapping):
            continue
        record = catalyst_record(
            type=str(row.get("type") or ""),
            event_time=row.get("event_time"),
            available_at=row.get("available_at"),
            source=row.get("source"),
            summary=row.get("summary"),
            confidence=row.get("confidence"),
            direction=row.get("direction"),
            extras={k: v for k, v in row.items() if k not in {
                "type", "event_time", "available_at", "source", "summary", "confidence", "direction",
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


def bearish_catalysts(rows: Sequence[Mapping[str, Any]] | None, *, now: datetime | None = None) -> list[dict[str, Any]]:
    eligible = eligible_catalysts(rows, now=now) if now is not None else [
        row for row in (rows or ()) if isinstance(row, Mapping)
    ]
    return [row for row in eligible if str(row.get("direction") or "").upper() == "BEARISH"]


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
        direction="BEARISH",
        event_time=day,
        available_at=day,
        source=str(row.get("source") or "earnings-surprise"),
        summary=f"Reported EPS {actual_n} missed estimate {estimate_n}",
        confidence="MEDIUM",
        extras={
            "availability_basis": "report date treated as available_at; intraday publication time unknown",
            "actual_eps": actual_n,
            "estimated_eps": estimate_n,
        },
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
    items = parse_sec_items(row.get("items"))
    accession = str(row.get("accessionNumber") or row.get("accn") or "").strip()
    source = str(row.get("source") or accession or "sec.submissions")
    if form in {"S-1", "S-1/A"}:
        kind, direction, summary = "S1", "UNKNOWN", f"{form} filed"
        matched = None
    elif form in {"S-3", "S-3/A"}:
        kind, direction, summary = "S3", "UNKNOWN", f"{form} filed"
        matched = None
    elif form in {"8-K", "8-K/A"}:
        matched_items = [(item, ITEM_SEMANTICS[item]) for item in items if item in ITEM_SEMANTICS]
        bearish = [pair for pair in matched_items if pair[1]["bearish_by_itself"]]
        chosen = (bearish or matched_items or [(None, None)])[0]
        if chosen[1] is None:
            kind, direction = "EIGHT_K", "UNKNOWN"
            summary = f"{form} items {', '.join(items)}".strip() if items else f"{form} filed"
            matched = None
        else:
            item, spec = chosen
            kind, direction = spec["type"], spec["direction"]
            summary = f"{form} Item {item} {spec['title']}"
            matched = item
    else:
        return None
    return catalyst_record(
        type=kind,
        direction=direction,
        event_time=available,
        available_at=available,
        source=source,
        summary=summary,
        confidence="MEDIUM" if matched or form.startswith("S-") else "LOW",
        extras={
            "form": form,
            "items": ", ".join(items) if items else None,
            "item": matched,
            "accession": accession or None,
            "bearish_by_itself": direction == "BEARISH",
        },
    )
