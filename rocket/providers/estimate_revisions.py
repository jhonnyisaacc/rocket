"""Same-fiscal-period estimate revisions. Present-day snapshots are not history."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from rocket.pit import parse_datetime
from rocket.providers.short_quality import revision_state
from rocket.store import ResearchStore

SNAPSHOT_STATE = "estimate_snapshots"
REVISION_HORIZON = timedelta(days=30)
HORIZON_TOLERANCE = timedelta(days=5)


def period_identity(row: Mapping[str, Any]) -> tuple[str, str] | None:
    period = str(row.get("period") or row.get("fiscal_period") or "").strip().lower()
    fiscal = str(row.get("date") or row.get("fiscal_date") or row.get("period_end") or "").strip()
    if not period or not fiscal:
        return None
    return period, fiscal[:10]


def estimates_from_payload(rows: Sequence[Mapping[str, Any]] | None, *, symbol: str, now: datetime,
                           source: str) -> list[dict[str, Any]]:
    snapshots = []
    for row in rows or ():
        identity = period_identity(row)
        if identity is None:
            continue
        period, fiscal = identity
        snapshots.append({
            "symbol": symbol.upper(),
            "period": period,
            "fiscal_date": fiscal,
            "eps": row.get("epsAvg") if row.get("epsAvg") is not None else row.get("estimatedEpsAvg"),
            "revenue": row.get("revenueAvg") if row.get("revenueAvg") is not None else row.get("estimatedRevenueAvg"),
            "event_time": now.isoformat(),
            "available_at": now.isoformat(),
            "source": source,
        })
    return snapshots


def persist_snapshots(store: ResearchStore | None, rows: Sequence[Mapping[str, Any]], *, now: datetime) -> None:
    if store is None or not rows:
        return
    state = dict(store.load_state(SNAPSHOT_STATE) or {})
    history = list(state.get("snapshots") or [])
    for row in rows:
        history.append(dict(row))
    store.save_state(SNAPSHOT_STATE, {"snapshots": history, "updated_at": now.isoformat()})


def _as_of(row: Mapping[str, Any]) -> datetime | None:
    try:
        return parse_datetime(row.get("available_at") or row.get("event_time"))
    except ValueError:
        return None


def compare_same_period(later: Mapping[str, Any], earlier: Mapping[str, Any], *, metric: str) -> dict[str, Any]:
    left, right = period_identity(later), period_identity(earlier)
    if left is None or right is None:
        return {"state": "UNKNOWN", "change": None, "reason": "period_identity_unknown"}
    if left != right:
        return {
            "state": "UNKNOWN",
            "change": None,
            "reason": "incompatible_fiscal_period",
            "later_period": list(left),
            "earlier_period": list(right),
        }
    observed = revision_state(later.get(metric), earlier.get(metric))
    observed.update({
        "metric": metric,
        "period": left[0],
        "fiscal_date": left[1],
        "later_available_at": later.get("available_at"),
        "earlier_available_at": earlier.get("available_at"),
        "source": later.get("source") or earlier.get("source"),
    })
    return observed


def revision_30d(
    snapshots: Sequence[Mapping[str, Any]],
    symbol: str,
    *,
    now: datetime,
    metric: str = "eps",
    horizon: timedelta = REVISION_HORIZON,
) -> dict[str, Any]:
    """Compare the same fiscal period about 30 days apart. No same-period pair stays UNKNOWN."""
    eligible = []
    for row in snapshots:
        if str(row.get("symbol") or "").upper() != symbol.upper():
            continue
        available = _as_of(row)
        if available is None or available > now:
            continue
        if period_identity(row) is None:
            continue
        eligible.append((available, row))
    eligible.sort(key=lambda item: item[0])
    current = next((row for available, row in reversed(eligible) if timedelta(0) <= now - available <= HORIZON_TOLERANCE + horizon), None)
    if current is None and eligible:
        current = eligible[-1][1]
    if current is None:
        return {"state": "UNKNOWN", "change": None, "reason": "no_current_snapshot", "historically_available": False}
    current_at = _as_of(current)
    target = current_at - horizon if current_at else None
    prior = None
    if target is not None:
        ranked = sorted(
            ((abs((available - target).total_seconds()), available, row) for available, row in eligible
             if period_identity(row) == period_identity(current) and available < current_at),
            key=lambda item: item[0],
        )
        if ranked and ranked[0][0] <= HORIZON_TOLERANCE.total_seconds():
            prior = ranked[0][2]
    if prior is None:
        return {
            "state": "UNKNOWN",
            "change": None,
            "reason": "no_same_period_prior_snapshot",
            "historically_available": False,
            "period": period_identity(current),
        }
    compared = compare_same_period(current, prior, metric=metric)
    compared["historically_available"] = compared.get("state") != "UNKNOWN" or compared.get("reason") != "incompatible_fiscal_period"
    return compared


def live_revisions(symbol: str, estimates: Sequence[Mapping[str, Any]] | None, *, store: ResearchStore | None,
                   now: datetime | None = None, source: str = "fmp.analyst-estimates") -> dict[str, Any]:
    decided = now or datetime.now(UTC)
    rows = estimates_from_payload(estimates, symbol=symbol, now=decided, source=source)
    persist_snapshots(store, rows, now=decided)
    history = list((store.load_state(SNAPSHOT_STATE) or {}).get("snapshots") or []) if store else rows
    eps = revision_30d(history, symbol, now=decided, metric="eps")
    revenue = revision_30d(history, symbol, now=decided, metric="revenue")
    return {
        "eps_revision_30d": eps.get("state"),
        "eps_revision_change": eps.get("change"),
        "revenue_revision_30d": revenue.get("state"),
        "revenue_revision_change": revenue.get("change"),
        "revision_reason": eps.get("reason") or revenue.get("reason"),
        "historically_available": bool(eps.get("historically_available") or revenue.get("historically_available")),
        "snapshots_persisted": len(rows),
        "availability_basis": "same fiscal period compared across stored snapshots; current API rows are not a revision history",
    }
