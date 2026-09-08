"""One local candidate index, shared by ISM, disclosures and Shorts."""

import hashlib
import math
from datetime import timedelta

from rocket.pit import parse_datetime


def candidate_id(ticker):
    return "listed:" + ticker.strip().upper()


def persist_candidates(store, origin, rows, *, now):
    if store is None:
        return
    state = dict(store.load_state("research_candidates") or {})
    entries = dict(state.get("candidates", {}))
    groups = {}
    for row in rows:
        groups.setdefault(candidate_id(row["ticker"]), []).append(row)
    for inputs in groups.values():
        row = dict(inputs[0])
        row["inputs"] = inputs
        if len({r["direction"] for r in inputs}) > 1:
            row.update(direction="unknown", classification="NEEDS_REVIEW", reason="Conflicting source directions require review")
        key = candidate_id(row["ticker"])
        existing = entries.get(key, {"candidate_id": key, "ticker": row["ticker"], "origins": {}})
        origins = dict(existing.get("origins", {}))
        origins[origin] = {**row, "available_at": now.isoformat(),
                           "expires_at": (now + timedelta(days=35 if origin == "ism" else 7)).isoformat()}
        entries[key] = {**existing, "origins": origins}
    store.save_state("research_candidates", {"candidates": entries, "updated_at": now.isoformat()})


def bearish_inputs(store, now):
    state = store.load_state("research_candidates") or {}
    result = []
    for row in state.get("candidates", {}).values():
        sources = []
        for r in row.get("origins", {}).values():
            try:
                available, expires = parse_datetime(r.get("available_at")), parse_datetime(r.get("expires_at"))
                if r.get("reference_month") and r.get("report_type"):
                    from rocket.providers.ism import expected_reference
                    if r["reference_month"] != expected_reference(r["report_type"], now).strftime("%Y-%m"):
                        continue
                if r.get("direction") == "short" and available and expires and available <= now < expires:
                    sources.append(r)
            except (ValueError, TypeError):
                continue
        if sources:
            result.append({"ticker": row["ticker"], "candidate_id": row["candidate_id"], "sources": sources,
                           "sector_etf": next((r["sector_etf"] for r in sources if r.get("sector_etf")), None)})
    return result


def overlap(store, ticker, *, portfolio=(), watches=()):
    sources = []
    if ticker in portfolio:
        sources.append("portfolio")
    if ticker in watches:
        sources.append("watch")
    state = store.load_state("research_candidates") or {} if store else {}
    row = state.get("candidates", {}).get(candidate_id(ticker), {})
    sources.extend(row.get("origins", {}))
    return sorted(set(sources))


def evaluate_long(ticker, context, *, thesis, source_reference, now):
    """Conservative research entry using existing 20-session technical context."""
    market = context.get("market_state", {})
    fundamental = context.get("fundamentals", {})
    technical = context.get("technical_basis", {})
    missing = []
    if context.get("meaningful_new_information"):
        missing.append("material reporting requires independent review before entry")
    from rocket.clock import equity_observation_fresh
    from rocket.pit import Availability, PointInTime
    from rocket.workflows.portfolio import positive_number

    try:
        pit = PointInTime(parse_datetime(market.get("as_of")), parse_datetime(market.get("available_at")), now)
        if pit.availability is not Availability.ELIGIBLE or not market.get("source") or not equity_observation_fresh(market.get("as_of"), now, daily=market.get("daily", True)):
            missing.append("current market evidence")
    except ValueError:
        missing.append("current market evidence")
    for name, value in (("price", market.get("current_price")), ("20-session average", technical.get("average_20")), ("invalidation", technical.get("low_20"))):
        if not positive_number(value):
            missing.append(name)
    try:
        available = parse_datetime(fundamental.get("available_at"))
        if available is None or not timedelta(0) <= now - available <= timedelta(days=7) or not fundamental.get("fundamentals_source"):
            missing.append("current fundamentals")
    except ValueError:
        missing.append("current fundamentals")
    if any(not isinstance(fundamental.get(k), (int, float)) or isinstance(fundamental.get(k), bool)
           or not math.isfinite(fundamental[k]) for k in ("eps_growth", "pe_ttm")):
        missing.append("EPS growth and valuation")
    row = {"candidate_id": candidate_id(ticker), "ticker": ticker, "direction": "long",
           "thesis": thesis, "source_reference": source_reference, "context": context,
           "classification": "NEEDS_REVIEW", "missing": missing, "watch_proposal": None,
           "current_price": market.get("current_price"), "invalidation": technical.get("low_20"),
           "research_only": True, "entry": None}
    if missing:
        return row
    price, average, low = market["current_price"], technical["average_20"], technical["low_20"]
    if fundamental["eps_growth"] < 0 or not 0 < fundamental["pe_ttm"] <= 40 or price <= low:
        row["classification"] = "NOT_INTERESTING"
    elif context.get("technical_condition") == "healthy" and average <= price <= average * 1.02 and low < price:
        row.update(classification="BUY_CANDIDATE", entry={"concept": "near 20-session support with positive reported EPS growth", "zone": [average, average * 1.02]})
    else:
        row["classification"] = "WATCH"
        row["watch_proposal"] = {"ticker": ticker, "condition": "ZONE", "zone": [average, average * 1.02],
                                 "thesis": thesis, "source_reference": source_reference,
                                 "requires_caller_approval": True}
    return row


def content_id(value):
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def caller_references():
    """Explicit caller files only; absent configuration is not an empty book."""
    import json
    from pathlib import Path

    from rocket.config import env
    values, coverage = {}, {}
    for name, variable, field in (("portfolio", "ROCKET_PORTFOLIO_STATE", "positions"), ("watch", "ROCKET_WATCH_STATE", "watches")):
        path = env(variable)
        values[name] = None
        coverage[name] = "NOT_CONFIGURED"
        if not path:
            continue
        try:
            data = json.loads(Path(path).expanduser().read_text())
            rows = data if isinstance(data, list) else data[field]
            if not isinstance(rows, list) or any(not isinstance(r, dict) or not r.get("ticker") for r in rows):
                raise ValueError("invalid caller reference file")
            values[name] = tuple(str(r["ticker"]).upper() for r in rows)
            coverage[name] = "AVAILABLE"
        except (OSError, ValueError, KeyError, TypeError):
            coverage[name] = "INVALID_CONFIGURATION"
    return values, coverage
