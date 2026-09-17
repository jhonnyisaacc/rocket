"""ISM short discovery: worst contracting industries, then reviewed equity exposure."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time
from typing import Any

from rocket.pit import parse_datetime

DEFAULT_CONTRACTING_LIMIT = 3
MAPPING_MODES = ("fixed", "strict_pit")


def _row(item: Any) -> dict[str, Any] | None:
    if isinstance(item, Mapping):
        industry = str(item.get("industry") or "").strip().lower()
        trend = str(item.get("trend") or "contracting").strip().lower()
        rank = item.get("rank")
    else:
        industry = str(getattr(item, "industry", "") or "").strip().lower()
        trend = str(getattr(item, "trend", "contracting") or "contracting").strip().lower()
        rank = getattr(item, "rank", None)
    if not industry:
        return None
    try:
        rank_n = int(rank) if rank is not None and not isinstance(rank, bool) else None
    except (TypeError, ValueError):
        rank_n = None
    return {"industry": industry, "trend": trend, "rank": rank_n}


def select_contracting_industries(
    industries: Sequence[Any] | None,
    *,
    limit: int = DEFAULT_CONTRACTING_LIMIT,
) -> list[dict[str, Any]]:
    """Up to `limit` worst contracting industries. Rank 1 is most contracting.

    Fewer than `limit` contracting industries are returned as-is. Manufacturing
    and Services stay distinct because the caller passes one series at a time.
    """
    if limit < 0:
        raise ValueError("limit must be >= 0")
    rows = []
    for item in industries or ():
        row = _row(item)
        if row is None or row["trend"] != "contracting":
            continue
        rows.append(row)
    rows.sort(key=lambda row: (row["rank"] is None, row["rank"] if row["rank"] is not None else 10**9))
    return rows[:limit]


def select_short_discovery(
    reports: Mapping[str, Mapping[str, Any]] | None,
    *,
    limit: int = DEFAULT_CONTRACTING_LIMIT,
) -> dict[str, list[dict[str, Any]]]:
    """Manufacturing and Services each contribute up to `limit` contracting industries."""
    selected: dict[str, list[dict[str, Any]]] = {}
    for kind in ("manufacturing", "services"):
        report = (reports or {}).get(kind) or {}
        selected[kind] = select_contracting_industries(report.get("worst_industries") or (), limit=limit)
    return selected


def mapping_available_at(row: Mapping[str, Any]) -> datetime | None:
    """Calendar date of `reviewed_at` at 00:00 UTC. Intra-day review time is unknown."""
    explicit = row.get("mapping_available_at") or row.get("available_at")
    if explicit:
        try:
            return parse_datetime(explicit)
        except ValueError:
            return None
    raw = str(row.get("reviewed_at") or "").strip()
    if not raw:
        return None
    try:
        day = date.fromisoformat(raw[:10])
    except ValueError:
        return None
    return datetime.combine(day, time.min, UTC)


def eligible_mappings(
    industry: str,
    exposures: Mapping[str, Sequence[Mapping[str, Any]]] | None,
    *,
    now: datetime | None = None,
    mapping_mode: str = "fixed",
) -> list[dict[str, Any]]:
    if mapping_mode not in MAPPING_MODES:
        raise ValueError(f"unsupported mapping_mode {mapping_mode!r}")
    matched = []
    for company in (exposures or {}).get(str(industry).strip().lower(), ()) or ():
        if not isinstance(company, Mapping):
            continue
        ticker = str(company.get("ticker") or "").strip().upper()
        if not ticker or not company.get("source") or not company.get("exposure"):
            continue
        available = mapping_available_at(company)
        if mapping_mode == "strict_pit":
            if now is None or available is None or available > now:
                continue
        matched.append({
            **dict(company),
            "ticker": ticker,
            "industry": str(industry).strip().lower(),
            "mapping_available_at": available.isoformat() if available else None,
            "mapping_mode": mapping_mode,
        })
    return matched


def build_short_universe(
    selected_by_kind: Mapping[str, Sequence[Mapping[str, Any]]],
    exposures: Mapping[str, Sequence[Mapping[str, Any]]] | None,
    *,
    now: datetime | None = None,
    mapping_mode: str = "fixed",
    reference_month: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Reviewed equities for selected ISM industries. One ticker may map to several themes."""
    seeds: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str, str]] = set()
    for kind, industries in selected_by_kind.items():
        for item in industries:
            parsed = _row(item)
            if parsed is None:
                continue
            industry, rank = parsed["industry"], parsed["rank"]
            mapped = eligible_mappings(industry, exposures, now=now, mapping_mode=mapping_mode)
            if not mapped:
                unmapped.append({
                    "industry": industry,
                    "report_type": kind,
                    "ism_rank": rank,
                    "reason": "no reviewed company exposure mapping",
                })
            for company in mapped:
                key = (company["ticker"], industry, str(kind))
                if key in seen:
                    continue
                seen.add(key)
                seed = {
                    **company,
                    "industry": industry,
                    "ism_rank": rank,
                    "report_type": kind,
                    "direction": "short",
                    "reference_month": (reference_month or {}).get(kind),
                    "classification": "SHORT_INPUT",
                    "requires_canonical_short_evaluation": True,
                }
                seeds.append(seed)
                by_ticker.setdefault(company["ticker"], []).append(seed)
    return {
        "seeds": seeds,
        "unmapped": unmapped,
        "by_ticker": by_ticker,
        "mapping_mode": mapping_mode,
        "universe_kind": "research",
    }


THEME_ATTRIBUTION_NOTE = "theme attribution is non-additive: one trade may appear in multiple theme buckets"


def primary_seed(seeds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """One ticker may map to several ISM themes; pick the worst rank as the primary seed."""
    rows = [dict(seed) for seed in seeds if str(seed.get("ticker") or "")]
    if not rows:
        raise ValueError("seeds required")
    return min(rows, key=lambda seed: (
        seed.get("ism_rank") is None,
        seed.get("ism_rank") if seed.get("ism_rank") is not None else 10**9,
        str(seed.get("industry") or ""),
    ))


def theme_keys(row: Mapping[str, Any]) -> list[str]:
    """Industry/theme keys for a single trade. Does not duplicate the trade."""
    keys: list[str] = []
    seen: set[str] = set()
    themes = row.get("themes")
    if not isinstance(themes, Sequence) or isinstance(themes, (str, bytes)):
        themes = []
    for theme in themes:
        if not isinstance(theme, Mapping):
            continue
        industry = str(theme.get("industry") or row.get("industry") or "").strip()
        report = str(theme.get("report_type") or row.get("report_type") or "").strip()
        if not industry:
            continue
        key = f"{report}:{industry}"
        if key not in seen:
            seen.add(key)
            keys.append(key)
    if not keys:
        industry = str(row.get("industry") or "").strip()
        if industry:
            keys.append(f"{row.get('report_type') or ''}:{industry}")
    return keys


def theme_attribution(signals: Sequence[Mapping[str, Any]], *, value_key: str = "short_20d") -> dict[str, Any]:
    """Bucket 20d (or other) returns by every ISM theme. n can sum above trade count."""
    import statistics
    from collections import defaultdict

    industry_pnl: dict[str, list[float]] = defaultdict(list)
    for row in signals:
        value = row.get(value_key)
        if value is None:
            continue
        for key in theme_keys(row):
            industry_pnl[key].append(value)
    industries = {
        key: {
            "n": len(vals),
            "mean_short_20d": statistics.fmean(vals),
            "median_short_20d": statistics.median(vals),
        }
        for key, vals in sorted(industry_pnl.items())
    }
    return {
        "industries": industries,
        "note": THEME_ATTRIBUTION_NOTE,
        "trade_count": len(signals),
        "attributed_rows": sum(row["n"] for row in industries.values()),
    }
