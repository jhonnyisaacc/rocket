"""Score the five frozen contracts on the measured Hyperliquid 1h tape.

This is not the 12-month replay. Bars before 2026-02-27 are never invented.
1h triggers and 1h fills use only opens in
[2026-02-27T00:00:00Z, 2026-09-23T08:00:00Z].
4h, 1d, and 1w prints the provider actually returned before that open are
warmup for the contracts that name those endpoints. pana-full builds 4h, 1d,
and Monday weeks from the 1h tape only.

No parameter search. No sixth contract. The live scan is not imported into
an order path. execution_enabled is not touched.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from rocket.models import OperationalStatus
from rocket.providers.hyperliquid import (
    fetch_candles,
    fetch_funding_history,
    fetch_perp_markets,
)
from rocket.workflows.crypto import stage_symbol

BAKEOFF_DIR = Path(__file__).resolve().parent
if str(BAKEOFF_DIR) not in sys.path:
    sys.path.insert(0, str(BAKEOFF_DIR))

import pana_frozen  # noqa: E402

CACHE = Path("/tmp/bakeoff-tape")
H = 3_600_000
H4 = 4 * H
DAY = 86_400_000
WEEK = 7 * DAY
TAPE_START = datetime(2026, 2, 27, tzinfo=UTC)
TAPE_LAST_OPEN = datetime(2026, 9, 23, 8, tzinfo=UTC)
TAPE_START_MS = int(TAPE_START.timestamp() * 1000)
TAPE_LAST_MS = int(TAPE_LAST_OPEN.timestamp() * 1000)
WARM_START = datetime(2025, 9, 23, tzinfo=UTC)
WARM_START_MS = int(WARM_START.timestamp() * 1000)
MIN_DAILY_NOTIONAL = 5_000_000
# Same quote-volume floor the live scan already uses. Applied to one
# completed daily bar: base volume * close. Not today's dayNtlVlm, OI, or spread.
ELAPSED_DAYS = (TAPE_LAST_OPEN - TAPE_START).total_seconds() / 86_400
ELAPSED_MONTHS = ELAPSED_DAYS / (365.25 / 12)
TAPE_HOURS = (TAPE_LAST_MS - TAPE_START_MS) / H

MONTH_STARTS = [
    datetime(2026, 2, 27, tzinfo=UTC),
    datetime(2026, 3, 1, tzinfo=UTC),
    datetime(2026, 4, 1, tzinfo=UTC),
    datetime(2026, 5, 1, tzinfo=UTC),
    datetime(2026, 6, 1, tzinfo=UTC),
    datetime(2026, 7, 1, tzinfo=UTC),
    datetime(2026, 8, 1, tzinfo=UTC),
    datetime(2026, 9, 1, tzinfo=UTC),
]


def ms(stamp: datetime) -> int:
    return int(stamp.timestamp() * 1000)


def iso(millis: int) -> str:
    return datetime.fromtimestamp(millis / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def month_index(millis: int) -> int | None:
    if millis < TAPE_START_MS or millis > TAPE_LAST_MS:
        return None
    starts = [ms(item) for item in MONTH_STARTS]
    chosen = None
    for index, start in enumerate(starts):
        if start <= millis:
            chosen = index
    return chosen


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def fetch_candle_rows(client: httpx.Client, coin: str, interval: str, start_ms: int, end_ms: int):
    cache = CACHE / f"{coin}_{interval}_{start_ms}_{end_ms}.json"
    cached = load_json(cache)
    if isinstance(cached, list):
        return cached
    last_error = "empty"
    for attempt in range(4):
        result = fetch_candles(coin, interval=interval, start_ms=start_ms, end_ms=end_ms, http=client)
        if result.status is OperationalStatus.HEALTHY:
            rows = [
                [int(row["timestamp_ms"]), row["open"], row["high"], row["low"], row["close"], row["volume"]]
                for row in result.records
            ]
            save_json(cache, rows)
            return rows
        last_error = result.failure_kind or "unavailable"
        time.sleep(0.8 * (attempt + 1))
    return {"error": last_error}


def as_bars(rows) -> list[dict]:
    if isinstance(rows, dict):
        return []
    out = []
    seen = set()
    for t, o, h, l, c, v in rows:
        t = int(t)
        if t in seen:
            continue
        seen.add(t)
        if h <= 0 or l <= 0 or c <= 0 or h < l:
            continue
        out.append({"t": t, "o": float(o), "h": float(h), "l": float(l), "c": float(c), "v": float(v)})
    out.sort(key=lambda bar: bar["t"])
    return out


def clip_tape_1h(bars: list[dict]) -> list[dict]:
    """Keep measured opens only. Drop anything before 2026-02-27, including HYPE's 22:00 bar."""
    kept = []
    for bar in bars:
        if bar["t"] < TAPE_START_MS or bar["t"] > TAPE_LAST_MS:
            continue
        if bar["t"] == TAPE_LAST_MS:
            kept.append({**bar, "h": bar["o"], "l": bar["o"], "c": bar["o"], "_fill_only": True})
        else:
            kept.append(dict(bar))
    return kept


def _funding_complete(buckets: dict[int, float], end_ms: int) -> bool:
    if not buckets:
        return False
    return max(buckets) >= end_ms - 2 * H


def paginate_funding(client: httpx.Client, coin: str, start_ms: int, end_ms: int) -> dict[int, float]:
    cache = CACHE / f"{coin}_funding_{start_ms}_{end_ms}.json"
    cached = load_json(cache)
    if isinstance(cached, dict) and cached.get("complete") and "buckets" in cached:
        return {int(k): float(v) for k, v in cached["buckets"].items()}
    buckets: dict[int, float] = {}
    cursor = start_ms
    pages = 0
    while cursor <= end_ms and pages < 40:
        result = None
        for attempt in range(5):
            result = fetch_funding_history(coin, start_ms=cursor, end_ms=end_ms, http=client)
            if result.status is OperationalStatus.HEALTHY and result.records:
                break
            time.sleep(1.5 * (attempt + 1))
        pages += 1
        if result is None or result.status is not OperationalStatus.HEALTHY or not result.records:
            break
        last = result.records[-1]["timestamp_ms"]
        for row in result.records:
            hour = int(row["timestamp_ms"]) // H * H
            buckets[hour] = float(row["funding_rate"])
        if len(result.records) < 500 or last + 1 <= cursor:
            break
        cursor = int(last) + 1
        time.sleep(0.35)
    complete = _funding_complete(buckets, end_ms)
    if complete:
        save_json(cache, {"buckets": {str(k): v for k, v in buckets.items()}, "pages": pages, "complete": True})
    else:
        print(f"  funding incomplete {coin} n={len(buckets)} pages={pages}", flush=True)
    return buckets


def funding_records(buckets: dict[int, float]) -> list[dict]:
    return [{"time": t, "fundingRate": rate} for t, rate in sorted(buckets.items())]


def last_completed_daily(daily: list[dict], at_ms: int) -> dict | None:
    chosen = None
    for bar in daily:
        if bar["t"] + DAY <= at_ms:
            chosen = bar
        else:
            break
    return chosen


def month_membership(daily_by_coin: dict[str, list[dict]]) -> dict[int, list[str]]:
    membership: dict[int, list[str]] = {}
    for index, start in enumerate(MONTH_STARTS):
        names = []
        at = ms(start)
        for coin, daily in sorted(daily_by_coin.items()):
            bar = last_completed_daily(daily, at)
            if bar is None:
                continue
            notional = bar["v"] * bar["c"]
            if notional >= MIN_DAILY_NOTIONAL:
                names.append(coin)
        membership[index] = names
    return membership


def eligible_at(membership: dict[int, set[str]], millis: int, coin: str) -> bool:
    index = month_index(millis)
    if index is None:
        return False
    return coin in membership[index]


def quintile_sides(rows: list[tuple[str, float]]) -> tuple[list[str], list[str]] | None:
    """(return, coin) ascending. Bottom and top size floor(n/5). None if n < 5."""
    if len(rows) < 5:
        return None
    ranked = sorted(rows, key=lambda item: (item[1], item[0]))
    width = len(ranked) // 5
    shorts = [coin for coin, _ret in ranked[:width]]
    longs = [coin for coin, _ret in ranked[-width:]]
    return longs, shorts


def trb_signals(daily: list[dict], h4: list[dict]) -> list[dict]:
    """Fresh 50-close breaks. Channel days closed at or before the signal 4h opens."""
    signals = []
    for index, bar in enumerate(h4):
        close_t = bar["t"] + H4
        if close_t < TAPE_START_MS or close_t > TAPE_LAST_MS:
            continue
        days = [item for item in daily if item["t"] + DAY <= bar["t"]]
        if len(days) < 50:
            continue
        window = days[-50:]
        hi = max(item["c"] for item in window)
        lo = min(item["c"] for item in window)
        prev = h4[index - 1]["c"] if index else None
        if bar["c"] > hi and (prev is None or prev <= hi):
            signals.append({"direction": 1, "close_t": close_t, "level": hi, "signal_t": bar["t"]})
        elif bar["c"] < lo and (prev is None or prev >= lo):
            signals.append({"direction": -1, "close_t": close_t, "level": lo, "signal_t": bar["t"]})
    return signals


def closed_before(bars: list[dict], decision_ms: int, step: int, lookback_ms: int | None = None) -> list[dict]:
    kept = []
    for bar in bars:
        if bar["t"] + step > decision_ms:
            continue
        if lookback_ms is not None and bar["t"] < decision_ms - lookback_ms:
            continue
        kept.append(bar)
    return kept


def to_stage_bars(bars: list[dict]) -> list[dict]:
    return [
        {"timestamp_ms": bar["t"], "open": bar["o"], "high": bar["h"], "low": bar["l"], "close": bar["c"]}
        for bar in bars
    ]


def index_by_t(bars: list[dict]) -> dict[int, dict]:
    return {bar["t"]: bar for bar in bars}


def bar_at(index: dict[int, dict], stamp: int) -> dict | None:
    bar = index.get(stamp)
    if bar is None:
        return None
    return bar


def net_full_exit(direction: int, entry: float, exit_px: float, bps: float, drag: float) -> float:
    gross = direction * (exit_px - entry)
    cost = entry * bps / 10_000
    return gross - cost - drag


def funding_drag(direction: int, entry: float, start_ms: int, end_ms: int, buckets: dict[int, float]):
    """Funding prints on hour buckets in (fill, exit]. A missing hour is incomplete. No zero-fill."""
    if end_ms <= start_ms:
        return 0.0, True
    total = 0.0
    t = (start_ms // H) * H + H
    while t <= end_ms:
        if t not in buckets:
            return None, False
        total += direction * buckets[t] * entry
        t += H
    return total, True


def max_drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in values:
        equity += value
        if equity > peak:
            peak = equity
        drop = equity - peak
        if drop < worst:
            worst = drop
    return worst


def union_fraction(intervals: list[tuple[int, int]]) -> float:
    if TAPE_HOURS <= 0:
        return 0.0
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        start = max(start, TAPE_START_MS)
        end = min(end, TAPE_LAST_MS)
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    covered = sum(end - start for start, end in merged)
    return covered / (TAPE_HOURS * H)


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def fmt_num(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def path_exit(bars: list[dict], direction: int, stop: float, target: float | None, path: str):
    """Whole-position stop then first target. Fill is bars[0] open. None if unresolved."""
    if not bars:
        return None
    d = direction

    def hit_open(price: float):
        if d * (price - stop) <= 0:
            return price, "stop", True
        if target is not None and d * (price - target) >= 0:
            return price, "target", True
        return None

    def barriers(price: float, at_open: bool):
        if d * (price - stop) <= 0:
            return (price if at_open else stop), "stop"
        if target is not None and d * (price - target) >= 0:
            return target, "target"
        return None

    for bar in bars:
        opened = hit_open(bar["o"])
        if opened is not None:
            price, reason, _at_open = opened
            flat_from = bar["t"]
            return {"exit": price, "reason": reason, "exit_t": bar["t"], "flat_from": flat_from}
        if bar.get("_fill_only"):
            return None
        vertices = [bar["o"], bar["l"], bar["h"], bar["c"]] if path == "OLHC" else [bar["o"], bar["h"], bar["l"], bar["c"]]
        for left, right in zip(vertices, vertices[1:]):
            levels = [stop] + ([target] if target is not None else [])
            ordered = sorted((level for level in levels if min(left, right) <= level <= max(left, right)), reverse=right < left)
            for level in ordered:
                found = barriers(level, False)
                if found is not None:
                    price, reason = found
                    return {"exit": price, "reason": reason, "exit_t": bar["t"], "flat_from": bar["t"] + H}
            found = barriers(right, False)
            if found is not None:
                price, reason = found
                return {"exit": price, "reason": reason, "exit_t": bar["t"], "flat_from": bar["t"] + H}
    return None


def _range_cell(lowers: list[float], uppers: list[float] | None) -> str:
    if not lowers:
        return "n/a"
    low = mean(lowers)
    if not uppers:
        return fmt_num(low, 3)
    high = mean(uppers)
    if high is None or abs(high - low) < 1e-12:
        return fmt_num(low, 3)
    return f"{fmt_num(low, 3)}..{fmt_num(high, 3)}"


def summarize_trades(trades: list[dict], book: list[str], windows: dict, *, r_contract: bool) -> dict:
    """Closed-trade means. R stays undefined when the contract has no stop."""
    enters = [trade for trade in trades if trade.get("entered")]
    closed = [trade for trade in enters if trade.get("closed")]
    by_exit = sorted(closed, key=lambda trade: (trade["exit_t"], trade["coin"], trade["entry_t"]))
    usable = [trade for trade in by_exit if not trade.get("funding_incomplete") and trade.get("ret20") is not None]
    r20 = [trade["r20"] for trade in usable if trade.get("r20") is not None]
    r40 = [trade["r40"] for trade in usable if trade.get("r40") is not None]
    r20_hi = [trade["r20_upper"] for trade in usable if trade.get("r20_upper") is not None]
    r40_hi = [trade["r40_upper"] for trade in usable if trade.get("r40_upper") is not None]
    ret20 = [trade["ret20"] for trade in usable]
    ret40 = [trade["ret40"] for trade in usable if trade.get("ret40") is not None]
    r_defined = bool(r_contract and r20)

    def window_counts(name: str) -> str:
        start, end, coin = windows[name]
        subset = [
            trade
            for trade in enters
            if start <= trade["entry_t"] <= end and (coin is None or trade["coin"] == coin)
        ]
        if coin is not None and coin not in book:
            return f"{coin}_not_in_scored_list"
        longs = sum(1 for trade in subset if trade["direction"] > 0)
        shorts = sum(1 for trade in subset if trade["direction"] < 0)
        return f"L {longs} / S {shorts}"

    intervals: dict[str, list[tuple[int, int]]] = {coin: [] for coin in book}
    for trade in enters:
        end_t = trade["exit_t"] if trade.get("closed") else trade.get("open_until", TAPE_LAST_MS)
        intervals.setdefault(trade["coin"], []).append((trade["entry_t"], end_t))
    fractions = [union_fraction(intervals.get(coin, [])) for coin in book]
    time_in = sum(fractions) / len(fractions) if fractions else None

    funding_excluded = sum(1 for trade in closed if trade.get("funding_incomplete"))
    unresolved = sum(1 for trade in enters if not trade.get("closed"))

    def r_cell(lowers: list[float], uppers: list[float]) -> str:
        if not r_contract:
            return "R_undefined_no_stop"
        if not lowers:
            if funding_excluded and closed:
                return "funding_incomplete"
            if unresolved and not closed:
                return "unresolved"
            return "n/a"
        return _range_cell(lowers, uppers)

    if r_defined:
        dd_label = fmt_num(max_drawdown(r20), 3)
        dd_note = "peak-to-trough of cumulative closed-trade net R at 20bps + funding, worse funding bound, ordered by exit time"
    else:
        dd_label = f"{fmt_num(max_drawdown(ret20), 3)} net_return_not_R" if ret20 else "n/a"
        dd_note = "peak-to-trough of cumulative closed-trade net return because this contract has no stop"
    return {
        "enter": len(enters),
        "trades_per_month": len(enters) / ELAPSED_MONTHS,
        "june": window_counts("june"),
        "hype": window_counts("hype"),
        "r20": r_cell(r20, r20_hi),
        "r40": r_cell(r40, r40_hi),
        "ret20": None if not ret20 else mean(ret20),
        "ret40": None if not ret40 else mean(ret40),
        "dd": dd_label,
        "dd_note": dd_note,
        "time_in_market": time_in,
        "closed": len(closed),
        "unresolved": unresolved,
        "funding_excluded": funding_excluded,
        "r_defined": r_defined,
        "admissions": None,
    }


# --- theory-v2 pure functions (code, not the docstring) ---

def _trend(closes: list[float], window: int, deadband: float = 0.005) -> str:
    if len(closes) < window + 1:
        return "neutral"
    ma = sum(closes[-window:]) / window
    last = closes[-1]
    if last > ma * (1 + deadband):
        return "long"
    if last < ma * (1 - deadband):
        return "short"
    return "neutral"


def _true_ranges(bars: list[dict]) -> list[float]:
    out = []
    prev = None
    for bar in bars:
        hl = bar["h"] - bar["l"]
        if prev is None:
            tr = hl
        else:
            tr = max(hl, abs(bar["h"] - prev), abs(bar["l"] - prev))
        out.append(tr)
        prev = bar["c"]
    if out:
        out[0] = None
    return out


def _atr(bars: list[dict], window: int) -> float | None:
    if len(bars) < window + 1:
        return None
    tr = _true_ranges(bars)
    window_tr = tr[-window:]
    if any(item is None for item in window_tr):
        return None
    value = sum(window_tr) / window
    return value if value > 0 else None


def momentum_bias(weekly: list[dict]) -> tuple[str, float | None]:
    lookback, min_velocity, atr_window = 4, 1.2, 8
    if len(weekly) < max(lookback + 1, atr_window + 1):
        return "neutral", None
    atr = _atr(weekly, atr_window)
    if atr is None:
        return "neutral", None
    closes = [bar["c"] for bar in weekly]
    velocity = (closes[-1] - closes[-lookback - 1]) / atr
    if velocity > min_velocity:
        return "long", velocity
    if velocity < -min_velocity:
        return "short", velocity
    return "neutral", velocity


def range_breakout_bias(weekly: list[dict]) -> str:
    range_window, max_range_atrs, buffer_atrs, atr_window = 8, 1.5, 0.5, 8
    if len(weekly) < max(range_window + 1, atr_window + 1):
        return "neutral"
    atr = _atr(weekly, atr_window)
    if atr is None:
        return "neutral"
    closes = [bar["c"] for bar in weekly]
    prior = closes[-range_window:-1]
    if not prior:
        return "neutral"
    range_high = max(prior)
    range_low = min(prior)
    if (range_high - range_low) / atr > max_range_atrs:
        return "neutral"
    last = closes[-1]
    if last > range_high + buffer_atrs * atr:
        return "long"
    if last < range_low - buffer_atrs * atr:
        return "short"
    return "neutral"


def climax_blocks(daily: list[dict]) -> bool:
    atr_window, climax_mult, cooldown = 20, 3.0, 10
    if len(daily) < atr_window + 2:
        return False
    tr = _true_ranges(daily)
    last_idx = len(daily) - 1
    earliest = max(0, last_idx - cooldown + 1)
    for i in range(last_idx, earliest - 1, -1):
        window = tr[i - atr_window + 1 : i + 1]
        if len(window) < atr_window or any(item is None for item in window):
            continue
        atr_i = sum(window) / atr_window
        if atr_i <= 0:
            continue
        if tr[i] > climax_mult * atr_i:
            return (last_idx - i) < cooldown
    return False


def find_impulse_leg(daily: list[dict]):
    lookback, swing = 60, 5
    if len(daily) < lookback or len(daily) < 2 * swing + 1:
        return None
    sub = daily[-lookback:]
    highs = [bar["h"] for bar in sub]
    lows = [bar["l"] for bar in sub]
    swing_highs = []
    swing_lows = []
    for i in range(swing, len(sub) - swing):
        win_h = highs[i - swing : i + swing + 1]
        win_l = lows[i - swing : i + swing + 1]
        if highs[i] == max(win_h) and win_h.count(highs[i]) == 1:
            swing_highs.append((i, highs[i]))
        if lows[i] == min(win_l) and win_l.count(lows[i]) == 1:
            swing_lows.append((i, lows[i]))
    if not swing_highs or not swing_lows:
        return None
    return swing_lows[-1][1], swing_highs[-1][1], swing_lows[-1][0], swing_highs[-1][0]


def chase_ok(daily: list[dict], bias: str) -> bool:
    leg = find_impulse_leg(daily)
    if leg is None:
        return True
    low, high, low_idx, high_idx = leg
    if high <= low:
        return True
    last = daily[-1]["c"]
    span = high - low
    if bias == "long":
        if high_idx < low_idx:
            return True
        retrace = (high - last) / span
    else:
        if low_idx < high_idx:
            return True
        retrace = (last - low) / span
    return 0.50 <= retrace <= 0.95


def swing_targets(daily: list[dict], bias: str, entry: float) -> list[float]:
    lookback, swing = 60, 5
    if len(daily) < 2 * swing + 1:
        return []
    sub = daily[-lookback:]
    highs = [bar["h"] for bar in sub]
    lows = [bar["l"] for bar in sub]
    targets = []
    for i in range(swing, len(sub) - swing):
        if bias == "long":
            win = highs[i - swing : i + swing + 1]
            if highs[i] == max(win) and win.count(highs[i]) == 1 and highs[i] > entry:
                targets.append(highs[i])
        else:
            win = lows[i - swing : i + swing + 1]
            if lows[i] == min(win) and win.count(lows[i]) == 1 and lows[i] < entry:
                targets.append(lows[i])
    uniq = sorted(set(targets), reverse=bias == "short")
    return uniq


def one_h_geometry(h1: list[dict], bias: str, daily: list[dict]):
    if len(h1) < 24 or bias == "neutral":
        return None
    entry = h1[-1]["c"]
    window = h1[-24:]
    hi = max(bar["h"] for bar in window)
    lo = min(bar["l"] for bar in window)
    structural = entry - lo if bias == "long" else hi - entry
    if structural <= 0:
        return None
    risk = structural
    atr = _atr(daily, 14)
    if atr is not None:
        risk = max(structural, 1.5 * atr)
    stop = entry - risk if bias == "long" else entry + risk
    targets = []
    min_target = entry + risk if bias == "long" else entry - risk
    for price in swing_targets(daily, bias, entry):
        if bias == "long" and price >= min_target:
            targets.append(price)
        elif bias == "short" and price <= min_target:
            targets.append(price)
        if len(targets) >= 2:
            break
    if len(targets) == 0:
        if bias == "long":
            targets = [entry + 1.5 * risk, entry + 2.5 * risk]
        else:
            targets = [entry - 1.5 * risk, entry - 2.5 * risk]
    elif len(targets) == 1:
        if bias == "long":
            targets.append(max(targets[0] + risk, entry + 2.5 * risk))
        else:
            targets.append(min(targets[0] - risk, entry - 2.5 * risk))
    return stop, targets[0]


def theory_stage(weekly, daily, h4, h1) -> str:
    bias, _velocity = momentum_bias(weekly)
    if bias == "neutral":
        bias = range_breakout_bias(weekly)
    if bias == "neutral":
        return "weekly"
    closes_d = [bar["c"] for bar in daily]
    if _trend(closes_d, 10) != bias:
        return "daily"
    if climax_blocks(daily):
        return "climax_cooldown"
    if not chase_ok(daily, bias):
        return "chase_gate"
    if _trend([bar["c"] for bar in h4], 8) != bias:
        return "4H"
    if one_h_geometry(h1, bias, daily) is None:
        return "1H"
    return "fired"


def attach_costs(trade: dict, buckets: dict[int, float], r_defined: bool) -> None:
    if not trade.get("closed"):
        trade["r_defined"] = r_defined
        return
    drag, complete = funding_drag(trade["direction"], trade["entry"], trade["entry_t"], trade["exit_t"], buckets)
    trade["funding_incomplete"] = not complete
    trade["r_defined"] = r_defined and trade["direction"] * (trade["entry"] - trade["stop"]) > 0 if r_defined else False
    if not complete or drag is None:
        return
    for bps, rkey, retkey in ((20, "r20", "ret20"), (40, "r40", "ret40")):
        net = net_full_exit(trade["direction"], trade["entry"], trade["exit"], bps, drag)
        trade[retkey] = net / trade["entry"]
        risk = trade["direction"] * (trade["entry"] - trade["stop"]) if trade.get("stop") is not None else None
        if r_defined and risk is not None and risk > 0:
            trade[rkey] = net / risk
            trade["r_defined"] = True
        else:
            trade["r_defined"] = False


def score_trb(book, data, buckets, membership) -> dict:
    trades = []
    admissions = 0
    for coin in book:
        signals = trb_signals(data[coin]["1d"], data[coin]["4h"])
        hours = index_by_t(data[coin]["1h"])
        for signal in signals:
            if not eligible_at(membership, signal["close_t"], coin):
                continue
            admissions += 1
            fill = bar_at(hours, signal["close_t"])
            if fill is None or fill["t"] < TAPE_START_MS or fill["t"] > TAPE_LAST_MS:
                continue
            exit_due = signal["close_t"] + 10 * DAY
            exit_bar = None
            for bar in data[coin]["1h"]:
                if bar["t"] >= exit_due and bar["t"] <= TAPE_LAST_MS:
                    exit_bar = bar
                    break
            trade = {
                "coin": coin,
                "direction": signal["direction"],
                "entry": fill["o"],
                "entry_t": fill["t"],
                "entered": True,
                "stop": None,
                "r_defined": False,
                "closed": exit_bar is not None,
            }
            if exit_bar is not None:
                trade["exit"] = exit_bar["o"]
                trade["exit_t"] = exit_bar["t"]
                attach_costs(trade, buckets.get(coin, {}), False)
            else:
                trade["open_until"] = TAPE_LAST_MS
            trades.append(trade)
    return trades, admissions


def score_cmom(book, data, buckets, membership) -> tuple[list[dict], int, str | None]:
    week_sets = {coin: data[coin]["1w"] for coin in book}
    if not any(week_sets.values()):
        return [], 0, "no venue 1w candles for the scored list"
    close_times = sorted({bar["t"] + WEEK for bars in week_sets.values() for bar in bars})
    close_times = [t for t in close_times if TAPE_START_MS - WEEK <= t <= TAPE_LAST_MS + WEEK]
    admissions = 0
    events = []
    clocks = []
    block = None
    for week_close in close_times:
        h4_close = ((week_close + H4 - 1) // H4) * H4
        if h4_close > TAPE_LAST_MS or h4_close < TAPE_START_MS:
            continue
        if not any(bar["t"] + H4 == h4_close for coin in book for bar in data[coin]["4h"]):
            continue
        clocks.append(h4_close)
        rows = []
        for coin in book:
            if not eligible_at(membership, h4_close, coin):
                continue
            weeks = [bar for bar in week_sets[coin] if bar["t"] + WEEK <= week_close]
            if len(weeks) < 4:
                continue
            ret = weeks[-1]["c"] / weeks[-4]["c"] - 1
            rows.append((coin, ret))
        sides = quintile_sides(rows)
        if sides is None:
            continue
        longs, shorts = sides
        for coin, direction in [(name, 1) for name in longs] + [(name, -1) for name in shorts]:
            admissions += 1
            events.append({"coin": coin, "direction": direction, "fill_t": h4_close, "week_close": week_close})
    if admissions == 0 and block:
        return [], 0, block
    clock_set = sorted(set(clocks))
    trades = []
    for event in events:
        coin = event["coin"]
        hours = index_by_t(data[coin]["1h"])
        fill = bar_at(hours, event["fill_t"])
        if fill is None:
            continue
        exit_t = next((stamp for stamp in clock_set if stamp > event["fill_t"]), None)
        exit_bar = bar_at(hours, exit_t) if exit_t is not None else None
        trade = {
            "coin": coin,
            "direction": event["direction"],
            "entry": fill["o"],
            "entry_t": fill["t"],
            "entered": True,
            "stop": None,
            "r_defined": False,
            "closed": exit_bar is not None,
        }
        if exit_bar is not None:
            trade["exit"] = exit_bar["o"]
            trade["exit_t"] = exit_bar["t"]
            attach_costs(trade, buckets.get(coin, {}), False)
        else:
            trade["open_until"] = TAPE_LAST_MS
        trades.append(trade)
    return trades, admissions, None


def score_staged(book, data, buckets, membership) -> tuple[list[dict], int]:
    trades = []
    admissions = 0
    lookback_4h = 14 * DAY
    lookback_1d = 120 * DAY
    lookback_1w = 210 * DAY
    for coin in book:
        h4 = data[coin]["4h"]
        hours = index_by_t(data[coin]["1h"])
        prev = None
        open_trade = None
        for bar in h4:
            decision = bar["t"] + H4
            if decision > TAPE_LAST_MS:
                break
            d4 = closed_before(h4, decision, H4, lookback_4h)
            d1 = closed_before(data[coin]["1d"], decision, DAY, lookback_1d)
            w1 = closed_before(data[coin]["1w"], decision, WEEK, lookback_1w)
            liquid = eligible_at(membership, decision, coin) if TAPE_START_MS <= decision <= TAPE_LAST_MS else False
            # Before the tape, still compute state so an ongoing ZONE is not a fresh entry.
            if decision < TAPE_START_MS:
                liquid = True
            stage = stage_symbol(
                bars_4h=to_stage_bars(d4),
                bars_1d=to_stage_bars(d1),
                bars_1w=to_stage_bars(w1),
                decision_time=datetime.fromtimestamp(decision / 1000, UTC),
                eligible_liquid=liquid if decision < TAPE_START_MS or eligible_at(membership, decision, coin) else False,
                cot_regime="neutral",
            )
            state = stage["state"]
            direction = stage["direction"]
            origin = stage["invalidation"]
            beyond = False
            if open_trade is not None and origin is not None and open_trade.get("origin") is not None:
                beyond = open_trade["direction"] * (bar["c"] - open_trade["origin"]) < 0
            left = open_trade is not None and (
                state != "ZONE" or direction != ("long" if open_trade["direction"] > 0 else "short") or beyond
            )
            if left and decision >= TAPE_START_MS:
                fill = bar_at(hours, decision)
                if fill is not None and fill["t"] <= TAPE_LAST_MS:
                    open_trade["closed"] = True
                    open_trade["exit"] = fill["o"]
                    open_trade["exit_t"] = fill["t"]
                    attach_costs(open_trade, buckets.get(coin, {}), True)
                else:
                    open_trade["open_until"] = TAPE_LAST_MS
                open_trade = None
            fresh = state == "ZONE" and direction in {"long", "short"} and prev != ("ZONE", direction)
            if fresh and TAPE_START_MS <= decision <= TAPE_LAST_MS and eligible_at(membership, decision, coin):
                admissions += 1
                fill = bar_at(hours, decision)
                if fill is not None and open_trade is None and origin is not None:
                    side = 1 if direction == "long" else -1
                    trade = {
                        "coin": coin,
                        "direction": side,
                        "entry": fill["o"],
                        "entry_t": fill["t"],
                        "entered": True,
                        "stop": float(origin),
                        "origin": float(origin),
                        "r_defined": True,
                        "closed": False,
                        "open_until": TAPE_LAST_MS,
                    }
                    risk = side * (trade["entry"] - trade["stop"])
                    if risk > 0:
                        trades.append(trade)
                        open_trade = trade
                    else:
                        trade["entered"] = False
            if decision >= TAPE_START_MS or state == "ZONE":
                prev = (state, direction if state == "ZONE" else None)
            else:
                prev = (state, direction if state == "ZONE" else None)
        if open_trade is not None and not open_trade.get("closed"):
            open_trade["open_until"] = TAPE_LAST_MS
    return trades, admissions


def theory_fires(coin: str, data_coin: dict, membership) -> tuple[list[dict], int]:
    hours = [bar for bar in data_coin["1h"] if not bar.get("_fill_only")]
    fires = []
    count = 0
    weekly = data_coin["1w"]
    daily = data_coin["1d"]
    h4 = data_coin["4h"]
    if len(hours) < 24:
        return [], 0
    for index in range(23, len(hours)):
        signal = hours[index]
        decision = signal["t"] + H
        if decision > TAPE_LAST_MS:
            break
        if not eligible_at(membership, decision, coin):
            continue
        h1 = hours[: index + 1]
        if h1[0]["t"] < TAPE_START_MS:
            continue
        w = closed_before(weekly, decision, WEEK, None)
        d = closed_before(daily, decision, DAY, None)
        f = closed_before(h4, decision, H4, None)
        if theory_stage(w, d, f, h1) != "fired":
            continue
        count += 1
        bias, _velocity = momentum_bias(w)
        if bias == "neutral":
            bias = range_breakout_bias(w)
        geom = one_h_geometry(h1, bias, d)
        if geom is None:
            continue
        stop, target = geom
        fires.append(
            {
                "coin": coin,
                "direction": 1 if bias == "long" else -1,
                "signal_t": signal["t"],
                "fill_t": decision,
                "stop": stop,
                "target": target,
            }
        )
    return fires, count


def score_theory_path(book, data, buckets, membership, path: str) -> tuple[list[dict], int]:
    trades = []
    fires_total = 0
    for coin in book:
        fires, count = theory_fires(coin, data[coin], membership)
        fires_total += count
        flat_from = TAPE_START_MS
        hours = data[coin]["1h"]
        by_t = index_by_t(hours)
        for fire in fires:
            if fire["fill_t"] < flat_from:
                continue
            fill = bar_at(by_t, fire["fill_t"])
            if fill is None or fill["t"] > TAPE_LAST_MS:
                continue
            if fire["direction"] * (fill["o"] - fire["stop"]) <= 0:
                continue
            later = [bar for bar in hours if bar["t"] >= fill["t"]]
            found = path_exit(later, fire["direction"], fire["stop"], fire["target"], path)
            trade = {
                "coin": coin,
                "direction": fire["direction"],
                "entry": fill["o"],
                "entry_t": fill["t"],
                "stop": fire["stop"],
                "entered": True,
                "r_defined": True,
                "closed": found is not None,
            }
            if found is None:
                trade["open_until"] = TAPE_LAST_MS
                flat_from = TAPE_LAST_MS + H
            else:
                trade["exit"] = found["exit"]
                trade["exit_t"] = found["exit_t"]
                attach_costs(trade, buckets.get(coin, {}), True)
                flat_from = found["flat_from"]
            trades.append(trade)
    return trades, fires_total


def score_pana_coin(coin: str, hours: list[dict], buckets: dict[int, float], membership) -> dict:
    frames = pana_frozen.compute_frames(hours)
    end_ms = TAPE_LAST_MS
    daily = pana_frozen.aggregate([bar for bar in hours if not bar.get("_fill_only")], pana_frozen.D, end_ms)
    states = pana_frozen.impulses(daily)
    funding = funding_records(buckets)
    admitted = 0
    entered = 0
    paths = {"OLHC": [], "OHLC": []}
    busy = 0
    seen = set()
    for frame in frames:
        if not frame["eligible"]:
            continue
        if not eligible_at(membership, frame["time"], coin):
            continue
        key = (frame["direction"], frame["leg"]["origin_t"])
        if frame["time"] < busy or key in seen:
            continue
        seen.add(key)
        admitted += 1
        invalid = [bar["t"] + pana_frozen.D for bar, state in zip(daily, states) if state and state["direction"] != frame["direction"]]
        entered_here = False
        end_times = []
        for path in ("OLHC", "OHLC"):
            result = pana_frozen.simulate(hours, frame, "flip", path, funding, invalid, None)
            end_times.append(result.get("end_time", frame["time"]))
            if "entry" not in result:
                continue
            entered_here = True
            econ = result.get("economics") or {}
            net20 = (econ.get("net") or {}).get("20")
            net40 = (econ.get("net") or {}).get("40")
            closed = bool(econ.get("completed"))
            trade = {
                "coin": coin,
                "direction": result["direction"],
                "entry": result["entry"],
                "entry_t": result["entry_time"],
                "stop": result.get("initial_stop"),
                "entered": True,
                "closed": closed,
                "r_defined": True,
                "exit_t": result.get("end_time"),
                "funding_incomplete": not closed or net20 is None,
            }
            if closed and net20 is not None and net40 is not None:
                trade["r20"] = net20["r_lower"]
                trade["r40"] = net40["r_lower"]
                trade["r20_upper"] = net20["r_upper"]
                trade["r40_upper"] = net40["r_upper"]
                trade["ret20"] = net20["notional_lower"]
                trade["ret40"] = net40["notional_lower"]
            else:
                trade["open_until"] = min(result.get("end_time", TAPE_LAST_MS), TAPE_LAST_MS)
            paths[path].append(trade)
        if entered_here:
            entered += 1
        if end_times:
            busy = max(end_times)
    return {"coin": coin, "admissions": admitted, "entered": entered, "paths": paths, "frames": len(frames)}


def observation_windows(data: dict) -> dict:
    btc_days = [
        bar
        for bar in data.get("BTC", {}).get("1d", [])
        if bar["t"] + DAY <= TAPE_LAST_MS
        and datetime(2026, 6, 1, tzinfo=UTC).timestamp() * 1000 <= bar["t"] < datetime(2026, 7, 1, tzinfo=UTC).timestamp() * 1000
    ] if "BTC" in data else []
    if btc_days:
        low_bar = min(btc_days, key=lambda bar: (bar["l"], bar["t"]))
        june_start = low_bar["t"]
    else:
        june_start = ms(datetime(2026, 6, 1, tzinfo=UTC))
        low_bar = None
    june_end = ms(datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC))
    hype_note = "HYPE daily history missing"
    hype_start, hype_end = 0, -1
    if "HYPE" in data and data["HYPE"]["1d"]:
        completed = [bar for bar in data["HYPE"]["1d"] if bar["t"] + DAY <= TAPE_LAST_MS]
        ath = max(completed, key=lambda bar: (bar["h"], -bar["t"])) if completed else None
        if ath is None:
            hype_note = "HYPE had no completed daily bar by the last measured 1h open"
            return {
                "june": (june_start, june_end, None),
                "hype": (hype_start, hype_end, "HYPE"),
                "june_note": (
                    f"BTC June 2026 daily low {low_bar['l']:.6g} on {iso(low_bar['t'])}; "
                    f"observation fills from that open through 2026-08-31T23:59:59Z"
                    if low_bar
                    else "BTC June 2026 daily bars missing"
                ),
                "hype_note": hype_note,
            }
        hype_start = ath["t"] - 7 * DAY
        hype_end = ath["t"] + 7 * DAY
        tape_high = max((bar["h"] for bar in data["HYPE"]["1h"] if not bar.get("_fill_only")), default=None)
        hype_note = (
            f"HYPE daily-high day open {iso(ath['t'])} high {ath['h']:.6g}; "
            f"window [{iso(hype_start)}, {iso(hype_end)}] intersected with the 1h tape; "
            f"1h tape high {tape_high:.6g}" if tape_high is not None else "no 1h tape high"
        )
        if ath["t"] < TAPE_START_MS:
            hype_note += ". That daily high is before the 1h tape; the overlap is the part of the 7-day window that falls inside the tape."
    return {
        "june": (june_start, june_end, None),
        "hype": (hype_start, hype_end, "HYPE"),
        "june_note": (
            f"BTC June 2026 daily low {low_bar['l']:.6g} on {iso(low_bar['t'])}; "
            f"observation fills from that open through 2026-08-31T23:59:59Z"
            if low_bar
            else "BTC June 2026 daily bars missing"
        ),
        "hype_note": hype_note,
    }


def render_row(name: str, summary: dict, extra: str = "") -> str:
    per_month = summary["trades_per_month"]
    per = "NO_SAMPLE" if summary.get("no_sample") else fmt_num(per_month, 2)
    enter = "NO_SAMPLE" if summary.get("no_sample") else str(summary["enter"])
    if summary.get("no_sample"):
        cells = ["NO_SAMPLE"] * 6
        return (
            f"| `{name}` | {enter} | {per} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {cells[4]} | {cells[5]} |"
        )
    time_in = summary["time_in_market"]
    time_cell = "n/a" if time_in is None else f"{100 * time_in:.1f}%"
    return (
        f"| `{name}` | {enter}{extra} | {per} | {summary['june']} | {summary['hype']} | "
        f"{summary['r20']} | {summary['r40']} | {summary['dd']} | {time_cell} |"
    )


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=60.0, headers={"User-Agent": "rocket-research"})
    markets = fetch_perp_markets(http=client)
    if markets.status is not OperationalStatus.HEALTHY:
        raise SystemExit("metaAndAssetCtxs unavailable")
    names = sorted({row["name"] for row in markets.records})
    end_ms = TAPE_LAST_MS + DAY
    daily_rows = {}
    print(f"daily fetch {len(names)}", flush=True)
    for index, coin in enumerate(names):
        rows = fetch_candle_rows(client, coin, "1d", WARM_START_MS, end_ms)
        daily_rows[coin] = as_bars(rows) if not isinstance(rows, dict) else []
        if index % 25 == 0:
            print(f"  daily {index}/{len(names)}", flush=True)
        time.sleep(0.02)
    membership_lists = month_membership(daily_rows)
    listed = sorted({coin for coins in membership_lists.values() for coin in coins})
    print("month-start names", len(listed), flush=True)
    month_note = (
        "Month-start list built from currently listed perps only (delisted names are absent from meta). "
        "A name is in a month when its last completed 1d bar at that month start has base_volume * close "
        f">= {MIN_DAILY_NOTIONAL:.0f}. OI and spread history are absent and were not filled from today's metaAndAssetCtxs. "
        "Not today's top 100."
    )
    if not listed:
        listed = names
        month_note = (
            "Month-start notional list was empty, so the scored list is every current perp with a 1h pull. "
            + month_note
        )
    data = {}
    no_1h = []
    for coin in listed:
        h1_rows = fetch_candle_rows(client, coin, "1h", TAPE_START_MS, TAPE_LAST_MS + H)
        h1 = clip_tape_1h(as_bars(h1_rows) if not isinstance(h1_rows, dict) else [])
        if len([bar for bar in h1 if not bar.get("_fill_only")]) < 24:
            no_1h.append(coin)
            continue
        h4 = as_bars(fetch_candle_rows(client, coin, "4h", WARM_START_MS, end_ms))
        w1 = as_bars(fetch_candle_rows(client, coin, "1w", ms(datetime(2024, 1, 1, tzinfo=UTC)), end_ms))
        data[coin] = {"1h": h1, "4h": h4, "1d": daily_rows.get(coin, []), "1w": w1}
        time.sleep(0.02)
    book = sorted(data)
    print("scored book", len(book), "no_1h", len(no_1h), flush=True)
    if "BTC" in data and data["BTC"]["1w"]:
        sample = data["BTC"]["1w"][:3]
        gaps = [data["BTC"]["1w"][i]["t"] - data["BTC"]["1w"][i - 1]["t"] for i in range(1, min(4, len(data["BTC"]["1w"])))]
        print("btc 1w", [iso(bar["t"]) for bar in sample], "gaps_ms", gaps, flush=True)
    membership = {index: set(coins) & set(book) for index, coins in membership_lists.items()}
    buckets = {}
    print("funding", len(book), flush=True)
    for index, coin in enumerate(book):
        buckets[coin] = paginate_funding(client, coin, TAPE_START_MS, TAPE_LAST_MS + H)
        if index % 10 == 0:
            print(f"  funding {index}/{len(book)} {coin} hours={len(buckets[coin])}", flush=True)
    client.close()
    windows = observation_windows(data)
    results = {}

    def pack(name, trades, admissions, r_contract: bool, note: str, error: str | None = None):
        if error:
            results[name] = {"error": error, "note": note}
            return
        if not r_contract:
            for trade in trades:
                trade["r20"] = None
                trade["r40"] = None
                trade["r20_upper"] = None
                trade["r40_upper"] = None
        summary = summarize_trades(trades, book, windows, r_contract=r_contract)
        summary["admissions"] = admissions
        summary["no_sample"] = admissions == 0
        summary["note"] = note
        if summary["no_sample"]:
            summary["enter"] = 0
        results[name] = summary

    try:
        trades, admissions = score_trb(book, data, buckets, membership)
        pack(
            "trb-50d",
            trades,
            admissions,
            False,
            "Overlapping 10-day events are not netted. R is undefined because the contract has no stop. "
            "Drawdown is the peak-to-trough of cumulative closed-trade net return.",
        )
    except Exception as exc:  # noqa: BLE001
        pack("trb-50d", [], 0, False, "", f"{type(exc).__name__}: {exc}")

    try:
        trades, admissions, err = score_cmom(book, data, buckets, membership)
        if err and admissions == 0 and not trades:
            pack("cmom-r3-quintile", [], 0, False, "", err)
        else:
            pack(
                "cmom-r3-quintile",
                trades,
                admissions,
                False,
                "Unweighted event mean because vintage market cap is missing (weight_unknown_do_not_equal_weight). "
                "Not the paper's value-weighted portfolio. R is undefined (no stop). "
                "Overlapping weekly events are not netted into one account.",
            )
    except Exception as exc:  # noqa: BLE001
        pack("cmom-r3-quintile", [], 0, False, "", f"{type(exc).__name__}: {exc}")

    try:
        trades, admissions = score_staged(book, data, buckets, membership)
        pack(
            "staged-zone-as-entry",
            trades,
            admissions,
            True,
            "R uses fill-to-stored-origin, the baseline's exit invalidation. One position per ZONE episode. "
            "Live lookbacks: 14d 4h, 120d 1d, 210d 1w. COT neutral does not drop ZONE.",
        )
    except Exception as exc:  # noqa: BLE001
        pack("staged-zone-as-entry", [], 0, True, "", f"{type(exc).__name__}: {exc}")

    for path in ("OLHC", "OHLC"):
        try:
            trades, fires = score_theory_path(book, data, buckets, membership, path)
            pack(
                f"theory-v2-code/{path}",
                trades,
                fires,
                True,
                "Flat at the tape start (no pre-tape 1h position was invented). "
                "Stop and first objective use both path orders. Whole position exits at the first objective "
                "(partials_unspecified_in_signal). COT history was not passed. "
                "Book wider than BTC/ETH is theory_v2_book_scope_interpretation. "
                "R is fill-to-the-code-stop.",
            )
        except Exception as exc:  # noqa: BLE001
            pack(f"theory-v2-code/{path}", [], 0, True, "", f"{type(exc).__name__}: {exc}")

    print("pana", len(book), flush=True)
    pana_paths = {"OLHC": [], "OHLC": []}
    pana_admissions = 0
    pana_entered = 0
    pana_error = None
    try:
        for index, coin in enumerate(book):
            print(f"  pana {index}/{len(book)} {coin}", flush=True)
            scored = score_pana_coin(coin, data[coin]["1h"], buckets.get(coin, {}), membership)
            pana_admissions += scored["admissions"]
            pana_entered += scored["entered"]
            for path, rows in scored["paths"].items():
                pana_paths[path].extend(rows)
    except Exception as exc:  # noqa: BLE001
        pana_error = f"{type(exc).__name__}: {exc}"
    if pana_error:
        pack("pana-full", [], 0, True, "", pana_error)
    else:
        for path, trades in pana_paths.items():
            pack(
                f"pana-full/{path}",
                trades,
                pana_admissions,
                True,
                "Flip path only. Partials 80/10/10 are inside the frozen economics. "
                "Net R uses the funding lower bound (r_lower); r_upper is stored on the trade and not selected as the result. "
                "Weeks are aggregated from the 1h tape only, so velocity cannot exist until nine Monday weeks exist after 2026-02-27. "
                "The last measured open does not run flip_step.",
            )
        results["pana-full"] = {
            "enter": pana_entered,
            "admissions": pana_admissions,
            "no_sample": pana_admissions == 0,
            "paths": {path: results.pop(f"pana-full/{path}") for path in ("OLHC", "OHLC")},
        }

    payload = {
        "tape_start": TAPE_START.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tape_last_open": TAPE_LAST_OPEN.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_days": ELAPSED_DAYS,
        "elapsed_months": ELAPSED_MONTHS,
        "book": book,
        "no_1h": no_1h,
        "month_counts": {iso(ms(MONTH_STARTS[i])): len(membership[i]) for i in membership},
        "month_names": {iso(ms(MONTH_STARTS[i])): sorted(membership[i]) for i in membership},
        "month_note": month_note,
        "june_note": windows["june_note"],
        "hype_note": windows["hype_note"],
        "first_opens": {coin: iso(data[coin]["1h"][0]["t"]) for coin in book},
        "last_opens": {coin: iso(data[coin]["1h"][-1]["t"]) for coin in book},
        "results": results,
    }
    save_json(CACHE / "summary.json", payload)
    print(json.dumps({k: payload[k] for k in ("elapsed_months", "book", "month_counts", "june_note", "hype_note")}, indent=2))
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
