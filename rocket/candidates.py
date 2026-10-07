"""One local candidate index, shared by ISM, disclosures and Shorts."""

import hashlib
import math
from collections.abc import Mapping
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


def evaluate_long(ticker, context, *, thesis, source_reference, now, entry_policy="reclaim"):
    """Conservative research entry using existing 20-session technical context."""
    market = context.get("market_state", {})
    fundamental = context.get("fundamentals", {})
    technical = context.get("technical_basis", {})
    if entry_policy == "ism_support":
        technical = technical.get("ism_daily_basis", technical)
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
    if entry_policy == "ism_support":
        from rocket.clock import NY, latest_completed_session

        if not positive_number(technical.get("latest_close")):
            missing.append("latest completed daily close")
        try:
            close_at = parse_datetime(technical.get("latest_close_at"))
            completed = close_at is not None and close_at.astimezone(NY).date() == latest_completed_session(now)
        except (ValueError, TypeError):
            completed = False
        if not completed or not equity_observation_fresh(technical.get("latest_close_at"), now, daily=True):
            missing.append("fresh completed daily close timestamp")
    try:
        available = parse_datetime(fundamental.get("available_at"))
        if available is None or not timedelta(0) <= now - available <= timedelta(days=7) or not fundamental.get("fundamentals_source"):
            missing.append("current fundamentals")
    except ValueError:
        missing.append("current fundamentals")
    if any(not isinstance(fundamental.get(k), (int, float)) or isinstance(fundamental.get(k), bool)
           or not math.isfinite(fundamental[k]) for k in ("eps_growth", "pe_ttm")):
        missing.append("EPS growth and valuation")
    disagreement = fundamental.get("eps_provider_disagreement")
    if isinstance(disagreement, Mapping) and disagreement.get("reason") == "opposite_sign":
        missing.append("EPS providers disagree on sign")
    row = {"candidate_id": candidate_id(ticker), "ticker": ticker, "direction": "long",
           "thesis": thesis, "source_reference": source_reference, "context": context,
           "classification": "NEEDS_REVIEW", "missing": missing, "watch_proposal": None,
           "current_price": market.get("current_price"),
           "invalidation": None if entry_policy == "ism_support" else technical.get("low_20"),
           "research_only": True, "entry": None}
    if entry_policy == "ism_support":
        # Preserve the pre-PR invalidation input under its actual meaning,
        # including non-passing rows; it is not the ATR research risk level.
        row["low_20_close"] = context.get("technical_basis", {}).get("low_20")
    if missing:
        return row
    price, average, low = market["current_price"], technical["average_20"], technical["low_20"]
    if entry_policy == "ism_support":
        return _ism_support_entry(row, fundamental, price=price, support=low)
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


def _ism_support_entry(row, fundamental, *, price, support):
    """ISM-only deterministic value band around prior 20-session closing support.

    Keep disclosures' reclaim policy and the canonical short gates independent.
    The completed snapshot excludes the assessed close from support, so a new
    closing low cannot silently move support down and erase the support veto.
    """
    if fundamental["eps_growth"] < 0 or not 0 < fundamental["pe_ttm"] <= 40:
        row.update(classification="NOT_INTERESTING", reason="EPS growth or valuation fails the long gate")
        return row
    from rocket.workflows.portfolio import positive_number

    technical = row["context"]["technical_basis"]
    technical = technical.get("ism_daily_basis", technical)
    raw_atr = technical.get("atr_14")
    atr = float(raw_atr) if positive_number(raw_atr) else None
    # Bound volatility units to 0.5–3% of support, avoiding near-zero bands
    # and excessively wide stops. Legacy/missing OHLC uses an explicit fallback.
    volatility = min(max(atr, support * 0.005), support * 0.03) if atr is not None else support * 0.02
    method = "low_20_atr_support" if atr is not None else "low_20_percent_fallback"
    zone = [support, support + volatility]
    invalidation = support - volatility * 1.5
    latest_close = technical.get("latest_close")
    buffer = volatility * 0.1
    buy_threshold = zone[1] - buffer
    breakdown = latest_close < support
    if breakdown:
        status = "WATCH"
        reason = f"closed below support {support:.2f}, wait for close back above support"
    elif latest_close <= buy_threshold:
        status = "BUY_CANDIDATE"
        reason = "completed daily close above support and within buffered entry zone; fundamentals pass"
    else:
        status = "WATCH"
        reason = (f"wait for pullback to {zone[0]:.2f}–{zone[1]:.2f}; "
                  f"completed daily close must be at or below {buy_threshold:.2f}")
    from rocket.clock import NY

    basis_date = parse_datetime(technical["latest_close_at"]).astimezone(NY).date().isoformat()
    reason += f"; as of {basis_date} close"
    # Signed distance to the nearest boundary: negative below, zero inside,
    # positive above. Denominator is the corresponding zone boundary.
    def zone_distance(value):
        return (value / zone[0] - 1) * 100 if value < zone[0] else (
            (value / zone[1] - 1) * 100 if value > zone[1] else 0.0)

    distance = zone_distance(latest_close)
    zone_position = "below_support" if latest_close < support else (
        "above_zone" if latest_close > zone[1] else "in_zone")
    row.update(classification=status, reason=reason, invalidation=invalidation,
               latest_completed_close=latest_close, latest_completed_close_at=technical["latest_close_at"],
               status_basis="latest_completed_daily_close", buy_close_threshold=buy_threshold,
               status_basis_date=basis_date, distance_pct=distance,
               zone_position=zone_position,
               intraday_price=price, intraday_distance_pct=zone_distance(price),
               entry_buffer_atr_fraction=0.1, raw_atr=atr,
               volatility_clamped=atr is not None and volatility != atr,
               entry_zone_low=zone[0], entry_zone_high=zone[1],
               distance_to_zone_pct=distance, breakdown_guard_failed=breakdown,
               entry={"concept": "prior 20-session closing support band",
                      "method": method, "support": support, "zone": zone,
                      "volatility_unit": volatility, "atr_14": atr,
                      "raw_atr": atr, "volatility_clamped": atr is not None and volatility != atr,
                      "buy_close_threshold": buy_threshold, "entry_buffer_atr_fraction": 0.1,
                      "invalidation": invalidation})
    if status == "WATCH":
        row["watch_proposal"] = {"ticker": row["ticker"], "condition": "ZONE", "zone": zone,
                                 "thesis": row["thesis"], "source_reference": row["source_reference"],
                                 "requires_caller_approval": True,
                                 "requires_stabilization": breakdown}
    return row


def content_id(value):
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def _reference_rows(path: str, field: str) -> tuple[tuple[str, ...] | None, str | None]:
    """Load ticker rows. The reason token is None when the file is a valid reference."""
    import json
    from pathlib import Path

    try:
        text = Path(path).expanduser().read_text(encoding="utf-8")
    except OSError:
        return None, "missing_file"
    except UnicodeDecodeError:
        return None, "malformed_json"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, "malformed_json"
    try:
        rows = data if isinstance(data, list) else data[field]
        invalid_row = not isinstance(rows, list) or any(
            not isinstance(row, dict) or not row.get("ticker") for row in rows
        )
        if invalid_row:
            raise ValueError("invalid caller reference file")
        return tuple(str(row["ticker"]).upper() for row in rows), None
    except (ValueError, KeyError, TypeError):
        return None, "schema"


def caller_references():
    """Explicit caller files only; absent configuration is not an empty book.

    ``coverage`` keeps ``portfolio`` and ``watch`` status strings. ``coverage["sources"]``
    names the env var that was consulted and, for an invalid path, a reason token.
    Paths and file contents are not included.
    """
    from rocket.config import ALIASES, env_source

    values, coverage, sources = {}, {}, {}
    for name, variable, field in (
        ("portfolio", "ROCKET_PORTFOLIO_STATE", "positions"),
        ("watch", "ROCKET_WATCH_STATE", "watches"),
    ):
        chosen, path = env_source(variable)
        values[name] = None
        if not chosen or not path:
            alias = next(iter(ALIASES.get(variable, ())), None)
            coverage[name] = "NOT_CONFIGURED"
            sources[name] = {"status": "NOT_CONFIGURED", "variable": variable, "alias": alias}
            continue
        tickers, reason = _reference_rows(path, field)
        if reason:
            coverage[name] = "INVALID_CONFIGURATION"
            sources[name] = {"status": "INVALID_CONFIGURATION", "variable": chosen, "reason": reason}
            continue
        values[name] = tickers
        coverage[name] = "AVAILABLE"
        sources[name] = {"status": "AVAILABLE", "variable": chosen}
    coverage["sources"] = sources
    return values, coverage


def reference_coverage_warnings(coverage: Mapping) -> tuple[str, ...]:
    """Name the unset or invalid reference setting. Never include a path or file body."""
    sources = coverage.get("sources") if isinstance(coverage, Mapping) else None
    if not isinstance(sources, Mapping):
        return ()
    messages = []
    for name in ("portfolio", "watch"):
        info = sources.get(name)
        if not isinstance(info, Mapping):
            continue
        variable = info.get("variable")
        if info.get("status") == "NOT_CONFIGURED":
            messages.append(
                f"{name} reference coverage NOT_CONFIGURED: set {variable} or {info.get('alias')}"
            )
        elif info.get("status") == "INVALID_CONFIGURATION":
            messages.append(
                f"{name} reference coverage INVALID_CONFIGURATION: {variable} {info.get('reason')}"
            )
    return tuple(messages)
