"""Forward labels label-v1: volatility-normalized triple barrier.

Reference: last completed 4h close P0 at candidate time. Scale S fixed at
candidate time (diffusion scale over LOOKBACK bars). Favorable barrier at
direction*log(P/P0) >= upper*S; adverse at <= -lower*S. First future 1h
OHLC touch wins. Decision-bar extrema excluded; bars starting before
decision_time excluded (first label bar starts cutoff+1h). Both-barrier
bar -> UNKNOWN; missing/incomplete horizon -> UNKNOWN, never censored
timeout. Full-window MAE/MFE always computed over the entire horizon.
"""

from __future__ import annotations

import math

from rocket.momentum import contracts


def label_candidate(
    event: dict,
    bars_1h: list[dict],
    *,
    horizon_days: int = contracts.HORIZON_PRIMARY_DAYS,
    upper: float = contracts.UPPER_MULT,
    lower: float = contracts.LOWER_MULT,
) -> dict:
    direction = event["direction"]
    sign = 1.0 if direction == "UP" else -1.0
    ref = event["reference_log"]
    scale = event["scale_S"]
    cutoff_ms = event["cutoff_ms"]
    horizon_ms = horizon_days * 24 * 3600 * 1000
    # First label bar opens at cutoff+1h (bars starting before decision_time
    # are excluded; decision_time = cutoff+5m falls inside [cutoff,cutoff+1h)).
    start_ms = cutoff_ms + 3600 * 1000
    end_ms = cutoff_ms + horizon_ms
    window = [b for b in bars_1h if start_ms <= b["open_ms"] < end_ms]
    # The excluded first post-cutoff hour leaves 24h-1 label bars per day.
    expected = horizon_days * 24 - 1
    outcome = "UNKNOWN"
    resolved_ms: int | None = None
    if len(window) == expected and scale > 0 and math.isfinite(scale):
        up_bar = upper * scale
        dn_bar = -lower * scale
        for bar in window:
            try:
                hi = sign * (math.log(bar["high"]) - ref)
                lo = sign * (math.log(bar["low"]) - ref)
            except (KeyError, TypeError, ValueError):
                outcome = "UNKNOWN"
                break
            hit_up = hi >= up_bar
            hit_dn = lo <= dn_bar
            if hit_up and hit_dn:
                outcome = "UNKNOWN"  # ambiguous intrabar order.
                resolved_ms = bar["open_ms"]
                break
            if hit_up:
                outcome = "CONTINUES"
                resolved_ms = bar["open_ms"]
                break
            if hit_dn:
                outcome = "FAILS"
                resolved_ms = bar["open_ms"]
                break
        else:
            outcome = "TIMEOUT"
    excursions = full_window_excursions(event, window if len(window) == expected else [])
    return {
        "cutoff_ms": cutoff_ms,
        "direction": direction,
        "horizon_days": horizon_days,
        "upper": upper,
        "lower": lower,
        "outcome": outcome,
        "resolved_ms": resolved_ms,
        "duration_bars": (
            (resolved_ms - start_ms) // (3600 * 1000) + 1
            if resolved_ms is not None and outcome in ("CONTINUES", "FAILS")
            else None
        ),
        "label_contract": contracts.LABEL_CONTRACT_VERSION,
        **excursions,
    }


def full_window_excursions(event: dict, window: list[dict]) -> dict:
    """MAE/MFE in log and S units plus signed end return over the window.

    Empty window -> UNKNOWN fields (never zero-filled).
    """
    direction = event["direction"]
    sign = 1.0 if direction == "UP" else -1.0
    ref = event["reference_log"]
    scale = event["scale_S"]
    if not window:
        return {
            "mfe_log": None,
            "mae_log": None,
            "mfe_S": None,
            "mae_S": None,
            "end_log": None,
            "end_S": None,
            "window_bars": 0,
        }
    try:
        signed_highs = [sign * (math.log(b["high"]) - ref) for b in window]
        signed_lows = [sign * (math.log(b["low"]) - ref) for b in window]
        end = sign * (math.log(window[-1]["close"]) - ref)
    except (KeyError, TypeError, ValueError):
        return {
            "mfe_log": None,
            "mae_log": None,
            "mfe_S": None,
            "mae_S": None,
            "end_log": None,
            "end_S": None,
            "window_bars": len(window),
        }
    mfe = max(signed_highs)
    mae = -min(signed_lows)  # adverse excursion as positive magnitude.
    if mae < 0:
        mae = 0.0
    return {
        "mfe_log": mfe,
        "mae_log": mae,
        "mfe_S": mfe / scale if scale > 0 else None,
        "mae_S": mae / scale if scale > 0 else None,
        "end_log": end,
        "end_S": end / scale if scale > 0 else None,
        "window_bars": len(window),
    }


def label_grid(event: dict, bars_1h: list[dict]) -> dict[str, dict]:
    """All predeclared sensitivity cells. No cell may replace primary."""
    out: dict[str, dict] = {}
    horizons = (contracts.HORIZON_PRIMARY_DAYS, *contracts.HORIZON_SENSITIVITY_DAYS)
    for days in horizons:
        for up, lo in contracts.SENSITIVITY_BARRIERS:
            key = f"{days}d_up{up}_lo{lo}"
            out[key] = label_candidate(event, bars_1h, horizon_days=days, upper=up, lower=lo)
    return out
