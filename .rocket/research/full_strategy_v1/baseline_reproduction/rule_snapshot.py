from __future__ import annotations
import math
STRUCTURE_BARS=6
MIN_SETUP_BARS=24
NO_CHASE_PCT=0.02
def _ohlc(bars: Sequence[Mapping[str, Any]]) -> list[dict[str, float]]:
    parsed: list[dict[str, float]] = []
    for bar in bars:
        try:
            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (high, low, close)) or high <= 0 or low <= 0 or close <= 0 or high < low:
            continue
        parsed.append({"high": high, "low": low, "close": close})
    return parsed

def structure_state(bars: Sequence[Mapping[str, float]]) -> str:
    window = list(bars)[-STRUCTURE_BARS:]
    if len(window) < STRUCTURE_BARS:
        return "INSUFFICIENT_DATA"
    highs = [row["high"] for row in window]
    lows = [row["low"] for row in window]
    higher = all(highs[index] > highs[index - 1] for index in range(1, len(highs))) and all(
        lows[index] > lows[index - 1] for index in range(1, len(lows))
    )
    lower = all(highs[index] < highs[index - 1] for index in range(1, len(highs))) and all(
        lows[index] < lows[index - 1] for index in range(1, len(lows))
    )
    if higher:
        return "HIGHER_HIGH_HIGHER_LOW"
    if lower:
        return "LOWER_HIGH_LOWER_LOW"
    return "MIXED"

def setup_from_candles(bars: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    """Conservative 4h structure setup. Missing bars stay invalid; nothing is imputed."""
    parsed = _ohlc(bars or ())
    if len(parsed) < MIN_SETUP_BARS:
        return {
            "valid": False,
            "reason": "insufficient_4h_history",
            "bars": len(parsed),
        }
    structure = structure_state(parsed)
    prior = parsed[-(STRUCTURE_BARS + 1) : -1]
    if len(prior) < STRUCTURE_BARS:
        return {
            "valid": False,
            "reason": "insufficient_4h_history",
            "bars": len(parsed),
        }
    close = parsed[-1]["close"]
    swing_high = max(row["high"] for row in prior)
    swing_low = min(row["low"] for row in prior)
    if structure == "HIGHER_HIGH_HIGHER_LOW":
        if close > swing_high * (1 + NO_CHASE_PCT):
            return {
                "valid": False,
                "reason": "extended_beyond_retest_band",
                "direction": "long",
                "structure": structure,
            }
        return {
            "valid": True,
            "direction": "long",
            "structure": structure,
            "entry_zone": [swing_low, (swing_low + swing_high) / 2],
            "invalidation": swing_low,
            "reason": None,
        }
    if structure == "LOWER_HIGH_LOWER_LOW":
        if close < swing_low * (1 - NO_CHASE_PCT):
            return {
                "valid": False,
                "reason": "extended_beyond_retest_band",
                "direction": "short",
                "structure": structure,
            }
        return {
            "valid": True,
            "direction": "short",
            "structure": structure,
            "entry_zone": [(swing_low + swing_high) / 2, swing_high],
            "invalidation": swing_high,
            "reason": None,
        }
    return {"valid": False, "reason": "mixed_or_insufficient_structure", "structure": structure}