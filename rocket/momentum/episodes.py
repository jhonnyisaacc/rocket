"""Episode grouping and ex-post leg segmentation (diagnostic only).

- Overlap components: crossings whose [cutoff, cutoff+horizon] intervals
  connect (transitively) form one component. Exposes clustering; the
  spaced (14d-cooldown) population is the conservative independent set.
- Ex-post legs: directional-change segmentation on 4h closes with a
  reversal threshold of 1S frozen at each extremum; a leg needs a
  completed reversal to close. Only legs with peak-to-trough magnitude
  >= 2S (S anchored at leg start) are 'large'. The unfinished last leg
  is censored. Legs never enter forecasting.
- Front-loading: for each large leg, fraction of the eventual log move
  completed at the first mechanical 1S advance observed on a closed 4h
  bar, then 4h/8h/12h later. Missed/late legs count as fully consumed.
"""

from __future__ import annotations

import math

from rocket.momentum import contracts
from rocket.momentum.candidates import log_returns, sample_sd


def overlap_components(
    events: list[dict], *, horizon_days: int = contracts.HORIZON_PRIMARY_DAYS
) -> list[list[int]]:
    """Connected components of overlapping label intervals (by index)."""
    horizon_ms = horizon_days * 24 * 3600 * 1000
    order = sorted(range(len(events)), key=lambda i: events[i]["cutoff_ms"])
    components: list[list[int]] = []
    current: list[int] = []
    current_end: int | None = None
    for idx in order:
        start = events[idx]["cutoff_ms"]
        end = start + horizon_ms
        if current_end is None or start > current_end:
            if current:
                components.append(current)
            current = [idx]
            current_end = end
        else:
            current.append(idx)
            current_end = max(current_end, end)
    if current:
        components.append(current)
    return components


def kish_effective_n(counts: list[int]) -> float:
    """Kish effective N over year counts: (sum w)^2 / sum w^2."""
    total = sum(counts)
    denom = sum(c * c for c in counts)
    if denom <= 0:
        return 0.0
    return total * total / denom


def segment_legs(bars_4h: list[dict]) -> list[dict]:
    """Directional-change legs on 4h closes. Reversal threshold 1S with S
    frozen at each extremum (sigma over trailing 181 closes at that bar).

    A leg closes only on a completed reversal; the last leg is censored.
    Only magnitude >= 2S legs (S anchored at leg start) are large.
    """
    closes = [b["close"] for b in bars_4h]
    logs = [math.log(c) for c in closes]
    legs: list[dict] = []
    if len(logs) < contracts.SIGMA_BARS + 2:
        return legs
    # Initial direction from first available move; extremum anchored at bar 0.
    start_idx = 0
    start_log = logs[0]
    rets = log_returns(closes[: contracts.SIGMA_BARS + 1])
    sig = sample_sd(rets)
    if sig is None or sig <= 0:
        return legs
    scale = sig * math.sqrt(contracts.LOOKBACK_BARS)
    direction = 0  # +1 up-leg, -1 down-leg, 0 undecided.
    extreme = start_log
    extreme_idx = 0
    for i in range(1, len(logs)):
        move = logs[i] - extreme
        if direction >= 0 and move >= scale:
            if direction == 0:
                direction = 1
            extreme = logs[i]
            extreme_idx = i
        elif direction <= 0 and move <= -scale:
            if direction == 0:
                direction = -1
            extreme = logs[i]
            extreme_idx = i
        elif direction == 1 and extreme - logs[i] >= scale:
            legs.append(_close_leg(bars_4h, logs, start_idx, extreme_idx, 1, scale))
            start_idx, start_log = extreme_idx, extreme
            rets = log_returns(closes[max(0, extreme_idx - contracts.SIGMA_BARS) : extreme_idx + 1])
            sig = sample_sd(rets) if len(rets) == contracts.SIGMA_BARS else None
            scale = sig * math.sqrt(contracts.LOOKBACK_BARS) if sig else scale
            direction, extreme, extreme_idx = -1, logs[i], i
        elif direction == -1 and logs[i] - extreme >= scale:
            legs.append(_close_leg(bars_4h, logs, start_idx, extreme_idx, -1, scale))
            start_idx, start_log = extreme_idx, extreme
            rets = log_returns(closes[max(0, extreme_idx - contracts.SIGMA_BARS) : extreme_idx + 1])
            sig = sample_sd(rets) if len(rets) == contracts.SIGMA_BARS else None
            scale = sig * math.sqrt(contracts.LOOKBACK_BARS) if sig else scale
            direction, extreme, extreme_idx = 1, logs[i], i
    # Censored last leg (unfinished by construction).
    legs.append(
        {
            "start_ms": bars_4h[start_idx]["open_ms"],
            "extreme_ms": bars_4h[extreme_idx]["open_ms"],
            "direction": direction,
            "magnitude_log": abs(extreme - start_log),
            "scale_S": scale,
            "magnitude_S": abs(extreme - start_log) / scale if scale > 0 else None,
            "large": bool(scale > 0 and abs(extreme - start_log) >= 2 * scale and direction != 0),
            "censored": True,
        }
    )
    return legs


def _close_leg(bars_4h, logs, start_idx, extreme_idx, direction, scale) -> dict:
    magnitude = abs(logs[extreme_idx] - logs[start_idx])
    return {
        "start_ms": bars_4h[start_idx]["open_ms"],
        "extreme_ms": bars_4h[extreme_idx]["open_ms"],
        "direction": direction,
        "magnitude_log": magnitude,
        "scale_S": scale,
        "magnitude_S": magnitude / scale if scale > 0 else None,
        "large": bool(scale > 0 and magnitude >= 2 * scale),
        "censored": False,
    }


def front_loading_for_leg(leg: dict, bars_4h: list[dict]) -> dict:
    """Fraction of the leg's eventual log move completed at first closed-4h
    1S advance, then 4h/8h/12h later. Missed/late legs count as consumed
    (fraction 1.0): optimistic ex-post conditional latency bound."""
    by_open = {b["open_ms"]: b for b in bars_4h}
    start = leg["start_ms"]
    extreme = leg["extreme_ms"]
    direction = leg["direction"]
    scale = leg["scale_S"]
    total = leg["magnitude_log"]
    out = {"leg_start_ms": start, "direction": direction, "total_log": total}
    if direction == 0 or not total or total <= 0 or not scale or scale <= 0:
        return {**out, "fractions": None, "note": "degenerate-leg"}
    sign = 1 if direction == 1 else -1
    start_log = math.log(by_open[start]["close"])
    target = start_log + sign * scale
    step = 4 * 3600 * 1000
    cursor = start + step
    confirm_ms: int | None = None
    while cursor <= extreme:
        bar = by_open.get(cursor)
        if bar is not None:
            hit = (math.log(bar["close"]) - target) * sign >= 0
            if hit:
                confirm_ms = cursor
                break
        cursor += step
    if confirm_ms is None:
        return {**out, "fractions": [1.0, 1.0, 1.0, 1.0], "note": "never-confirmed"}
    end_log = math.log(by_open[extreme]["close"])
    fracs = []
    for lag in (0, 1, 2, 3):
        bar = by_open.get(confirm_ms + lag * step)
        if bar is None:
            fracs.append(1.0)
            continue
        moved = (math.log(bar["close"]) - start_log) * sign
        frac = moved / ((end_log - start_log) * sign) if end_log != start_log else 1.0
        fracs.append(min(max(frac, 0.0), 1.0))
    return {**out, "fractions": fracs, "confirm_ms": confirm_ms, "note": "ok"}
