"""Feature definitions feat-v1: Tier A price baseline + Tier B crypto-market.

Reserved packet (MOM-001, NOT scored until gates pass and schema frozen):
Tier A (3): signed 24h log return / (sigma*sqrt(6)); short(6)/long(180)
RV ratio; relative 24h spot volume / preceding 30d average.
Tier B (3): signed trailing 24h realized funding sum; 24h log OI change;
spot/perp 24h quote-volume ratio. Max six variables, no transform search.
Missing B leaves UNKNOWN; no imputation, no live backfill, no dropping
of missing winners. Every feature records event_time/available_at and is
computable from data with available_at <= decision_time by construction
(callers pass only closed bars / published funding / daily metrics with
timestamp <= decision_time).
"""

from __future__ import annotations

import math

from rocket.momentum import contracts
from rocket.momentum.candidates import log_returns, sample_sd

SCHEMA = contracts.FEATURE_SCHEMA_VERSION
TIER_A = ("ret24_norm", "rv_ratio_6_180", "rel_volume_24h")
TIER_B = ("funding_24h_signed", "oi_change_24h", "spot_perp_volume_ratio")


def tier_a(bars_4h: list[dict], cutoff_ms: int, *, sigma: float) -> dict:
    """Price-only features from closed 4h bars with open < cutoff_ms."""
    closed = [b for b in bars_4h if b["open_ms"] < cutoff_ms]
    out = {"schema": SCHEMA, "tier": "A"}
    if sigma <= 0 or not math.isfinite(sigma) or len(closed) < 186:
        return {**out, **{k: None for k in TIER_A}, "missing": list(TIER_A)}
    last = closed[-6:]
    try:
        ret24 = math.log(last[-1]["close"] / last[0]["open"])
        rets_short = log_returns([b["close"] for b in closed[-7:]])
        rets_long = log_returns([b["close"] for b in closed[-181:]])
        vol24 = sum(b["volume"] for b in last)
        vol30d = sum(b["volume"] for b in closed[-186:-6])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return {**out, **{k: None for k in TIER_A}, "missing": list(TIER_A)}
    if len(rets_short) != 6 or len(rets_long) != 180 or vol30d <= 0:
        return {**out, **{k: None for k in TIER_A}, "missing": list(TIER_A)}
    sd_short = sample_sd(rets_short)
    sd_long = sample_sd(rets_long)
    if sd_short is None or sd_long is None or sd_long <= 0:
        return {**out, **{k: None for k in TIER_A}, "missing": list(TIER_A)}
    norm = sigma * math.sqrt(6)
    values = {
        "ret24_norm": ret24 / norm if norm > 0 else None,
        "rv_ratio_6_180": sd_short / sd_long,
        "rel_volume_24h": vol24 / (vol30d / 30.0),
    }
    missing = [k for k, v in values.items() if v is None or not math.isfinite(v)]
    return {**out, **values, "missing": missing}


def tier_b(
    funding: list[dict],
    metrics_daily: list[dict],
    spot_4h: list[dict],
    perp_4h: list[dict],
    cutoff_ms: int,
) -> dict:
    """Crypto-market features. Inputs pre-filtered to available_at <=
    decision_time by the caller. Daily metrics timestamped at day close;
    funding rows at calc_time. Anything absent -> None (UNKNOWN)."""
    out = {"schema": SCHEMA, "tier": "B"}
    day_ms = 24 * 3600 * 1000
    fund = [f for f in funding if f["ts_ms"] < cutoff_ms and f["ts_ms"] >= cutoff_ms - day_ms]
    funding_sum = sum(f["rate"] for f in fund) if fund else None
    day_idx = {(cutoff_ms - (i + 1) * day_ms) // day_ms for i in range(2)}
    # metrics_daily carries midnight-ms day stamps (possibly several intraday
    # snapshots per day in file order); compare in day-index units and let the
    # last row of a day win (end-of-day snapshot for complete past days).
    oi_by_day = {m["day"]: m.get("open_interest") for m in metrics_daily
                 if m["day"] // day_ms in day_idx}
    oi_change = None
    if len(oi_by_day) == 2 and all(v and v > 0 for v in oi_by_day.values()):
        vals = [oi_by_day[d] for d in sorted(oi_by_day)]
        try:
            oi_change = math.log(vals[1] / vals[0])
        except (TypeError, ValueError):
            oi_change = None
    step = 4 * 3600 * 1000
    spot_v = sum(b["quote_volume"] for b in spot_4h if cutoff_ms - 6 * step <= b["open_ms"] < cutoff_ms)
    perp_v = sum(b["quote_volume"] for b in perp_4h if cutoff_ms - 6 * step <= b["open_ms"] < cutoff_ms)
    ratio = spot_v / perp_v if spot_v > 0 and perp_v and perp_v > 0 else None
    values = {"funding_24h_signed": funding_sum, "oi_change_24h": oi_change,
              "spot_perp_volume_ratio": ratio}
    missing = [k for k, v in values.items() if v is None or not (isinstance(v, (int, float)) and math.isfinite(v))]
    return {**out, **values, "missing": missing}


def feature_row(event: dict, tier_a_vals: dict, tier_b_vals: dict) -> dict:
    """Combined row for modeling. Unknowns stay None; rows are never
    dropped for missingness here (model layer decides per protocol)."""
    row = {
        "cutoff_ms": event["cutoff_ms"],
        "direction": event["direction"],
        "schema": SCHEMA,
    }
    for source in (tier_a_vals, tier_b_vals):
        for key in (*TIER_A, *TIER_B):
            if key in source:
                row[key] = source[key]
    row["missing"] = sorted({k for k in (*TIER_A, *TIER_B) if row.get(k) is None})
    row["tier_b_missing"] = sorted({k for k in TIER_B if row.get(k) is None})
    return row


def parse_funding_csv(text: str) -> list[dict]:
    """Binance futures fundingRate CSV: calc_time, funding_interval_hours,
    last_funding_rate (tolerant to extra columns)."""
    import csv
    import io
    from datetime import UTC, datetime

    rows = []
    for fields in csv.reader(io.StringIO(text)):
        if not fields or not fields[0].strip().lstrip("-").isdigit():
            continue
        try:
            ts = int(fields[0])
            ts_ms = ts // 1000 if ts >= 10**16 else ts  # us- or ms-denominated.
            rate = float(fields[-1])
        except (TypeError, ValueError, IndexError):
            continue
        if not math.isfinite(rate):
            continue
        rows.append({"ts_ms": ts_ms, "rate": rate,
                     "timestamp": datetime.fromtimestamp(ts_ms / 1000, UTC).isoformat()})
    rows.sort(key=lambda r: r["ts_ms"])
    return rows


def parse_metrics_csv(text: str) -> list[dict]:
    """Binance futures daily metrics CSV: keyed lookup for open interest.

    Column names vary by era: current vendor files use snake_case
    (sum_open_interest, sum_open_interest_value); older captures used
    camelCase (sumOpenInterest, sumOpenInterestValue, openInterest).
    Prefer coin-denominated OI so the 24h log change isolates positioning
    change rather than mixing in the day's price move; fall back to
    notional value when only it is present. Day stamped at UTC midnight;
    available the next day.
    """
    import csv
    import io
    from datetime import UTC, datetime, timedelta

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return []
    cols = {name.strip(): i for i, name in enumerate(header)}
    oi_col = next((cols[c] for c in ("sum_open_interest", "sumOpenInterest", "sum_open_interest_value",
                                            "sumOpenInterestValue", "openInterest") if c in cols), None)
    time_col = next((cols[c] for c in ("create_time", "timestamp", "date", "calc_time") if c in cols), None)
    if oi_col is None or time_col is None:
        return []
    rows = []
    for fields in reader:
        try:
            raw = fields[time_col].strip()
            ts = int(raw) if raw.lstrip("-").isdigit() else None
            if ts is None:
                day = datetime.fromisoformat(raw[:10]).date()
            else:
                ts_ms = ts // 1000 if ts >= 10**16 else (ts * 1000 if ts < 10**12 else ts)
                day = datetime.fromtimestamp(ts_ms / 1000, UTC).date()
            oi = float(fields[oi_col])
        except (TypeError, ValueError, IndexError):
            continue
        if not math.isfinite(oi) or oi <= 0:
            continue
        day_epoch = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)
        rows.append({"day": day_epoch, "open_interest": oi,
                     "available_at": (datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=1)).isoformat()})
    return rows
