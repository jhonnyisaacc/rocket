"""Candidate generator candgen-v1: volatility-normalized Donchian crossing.

Population definer only, never scored as an edge. One deterministic rule:
at each 4h decision (cutoff at a UTC 4h boundary, decision = cutoff+5m),
sigma is the sample SD of the last 180 4h log-close returns including the
newly completed bar. UP fires when the decision-bar close exceeds the
highest high of the preceding 42 bars by >= 0.5 sigma (log price); DOWN
symmetrically. A new event requires an inactive->active crossing per side.
Flat/zero sigma or incomplete 30d history yields UNKNOWN, never a guess.
"""

from __future__ import annotations

import itertools
import math
from datetime import UTC, datetime

from rocket.momentum import contracts
from rocket.momentum.bars import contiguous_4h_before


def log_returns(closes: list[float]) -> list[float]:
    out = []
    for prev, cur in itertools.pairwise(closes):
        if prev <= 0 or cur <= 0:
            return []
        out.append(math.log(cur / prev))
    return out


def sample_sd(values: list[float]) -> float | None:
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    if not math.isfinite(var) or var < 0:
        return None
    return math.sqrt(var)


def sigma_at(bars_4h: list[dict]) -> float | None:
    """Sigma over the last SIGMA_BARS 4h log-close returns (needs 181 closes)."""
    need = contracts.SIGMA_BARS + 1
    if len(bars_4h) < need:
        return None
    closes = [b["close"] for b in bars_4h[-need:]]
    rets = log_returns(closes)
    if len(rets) != contracts.SIGMA_BARS:
        return None
    return sample_sd(rets)


def crossing_state(
    history: list[dict], *, sigma: float
) -> dict[str, str]:
    """Active/inactive per side for the decision bar (last bar of history).

    history must end with the decision bar and hold >= LOOKBACK_BARS + 1
    bars. Returns {'UP': state, 'DOWN': state} with states ACTIVE/INACTIVE.
    """
    if sigma <= 0 or not math.isfinite(sigma):
        return {"UP": "UNKNOWN", "DOWN": "UNKNOWN"}
    if len(history) < contracts.LOOKBACK_BARS + 1:
        return {"UP": "UNKNOWN", "DOWN": "UNKNOWN"}
    decision = history[-1]
    prior = history[-(contracts.LOOKBACK_BARS + 1) : -1]
    try:
        close = math.log(decision["close"])
        highs = [math.log(b["high"]) for b in prior]
        lows = [math.log(b["low"]) for b in prior]
    except (KeyError, TypeError, ValueError):
        return {"UP": "UNKNOWN", "DOWN": "UNKNOWN"}
    if any(not math.isfinite(v) for v in [close, *highs, *lows]):
        return {"UP": "UNKNOWN", "DOWN": "UNKNOWN"}
    tol = contracts.BREAK_PCT_SIGMA * sigma
    return {
        "UP": "ACTIVE" if close >= max(highs) + tol else "INACTIVE",
        "DOWN": "ACTIVE" if close <= min(lows) - tol else "INACTIVE",
    }


def scan_crossings(bars_4h: list[dict]) -> list[dict]:
    """Scan every eligible 4h decision; emit inactive->active crossings.

    Each decision requires full 30d contiguous history ending at its
    cutoff (decision bar = last complete bar). Emits raw crossing events
    (all reported); spacing into the independent set happens separately.
    """
    step_ms = 4 * 3600 * 1000
    by_open = {b["open_ms"]: b for b in bars_4h}
    if not bars_4h:
        return []
    first_cutoff = min(by_open) + (contracts.SIGMA_BARS + 1) * step_ms
    last_cutoff = max(by_open) + step_ms
    events: list[dict] = []
    prev_state = {"UP": "INACTIVE", "DOWN": "INACTIVE"}
    cutoff = first_cutoff - (first_cutoff % step_ms)
    if cutoff < first_cutoff:
        cutoff += step_ms
    while cutoff <= last_cutoff:
        hist = contiguous_4h_before(
            bars_4h, cutoff, min_bars=contracts.SIGMA_BARS + 1, by_open=by_open
        )
        cutoff += step_ms
        if not hist:
            prev_state = {"UP": "INACTIVE", "DOWN": "INACTIVE"}
            continue
        sig = sigma_at(hist)
        if sig is None or sig <= 0 or not math.isfinite(sig):
            prev_state = {"UP": "INACTIVE", "DOWN": "INACTIVE"}
            continue
        state = crossing_state(hist, sigma=sig)
        if state["UP"] == "UNKNOWN":
            prev_state = {"UP": "INACTIVE", "DOWN": "INACTIVE"}
            continue
        decision = hist[-1]
        ref = math.log(decision["close"])
        s = sig * math.sqrt(contracts.LOOKBACK_BARS)  # diffusion scale S.
        for side in contracts.DIRECTIONS:
            if state[side] == "ACTIVE" and prev_state[side] == "INACTIVE":
                events.append(
                    {
                        "cutoff_ms": decision["open_ms"] + step_ms,
                        "cutoff": datetime.fromtimestamp(
                            (decision["open_ms"] + step_ms) / 1000, UTC
                        ).isoformat(),
                        "decision_time": datetime.fromtimestamp(
                            (decision["open_ms"] + step_ms) / 1000
                            + contracts.DECISION_LAG_SECONDS,
                            UTC,
                        ).isoformat(),
                        "direction": side,
                        "reference_log": ref,
                        "reference_price": decision["close"],
                        "sigma": sig,
                        "scale_S": s,
                        "decision_close": decision["close"],
                        "generator": contracts.CANDIDATE_GENERATOR_VERSION,
                    }
                )
        prev_state = state
    return events


def space_candidates(events: list[dict]) -> list[dict]:
    """Global 14d cooldown: first crossing accepted, then suppress all
    crossings (either side) for 14d. Deterministic, never winner-dependent."""
    spaced: list[dict] = []
    last_accept_ms: int | None = None
    for event in sorted(events, key=lambda e: e["cutoff_ms"]):
        if last_accept_ms is None or event["cutoff_ms"] - last_accept_ms >= contracts.COOLDOWN_SECONDS * 1000:
            spaced.append({**event, "independent": True})
            last_accept_ms = event["cutoff_ms"]
        else:
            spaced.append({**event, "independent": False})
    return spaced
