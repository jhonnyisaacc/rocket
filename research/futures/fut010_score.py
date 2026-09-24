"""Score the frozen FUT-010 two-date Hyperliquid loss-close gross pilot.

Requires DuckDB. Only the two SHA-pinned 2025 Parquet shards in FUT-010 are
accepted. This is an optimistic trade-price proxy, not an executable fill.
"""

from __future__ import annotations

import argparse
import bisect
import collections
from datetime import UTC, datetime
import hashlib
import json
import random
from pathlib import Path

import duckdb


SOURCES = {
    "2025-07-28": "0fef107456e07dd63785f39b4366612071b1db1295ee03a0be6839ee77a66a69",
    "2025-10-10": "600e52955d8975614402f25404e141418a54a64e80ca0b016ebf44ccd82f703b",
}
SEGMENTS = (
    ("2025-07-28", "2025-07-28T14:00:00", "2025-07-28T18:00:00"),
    ("2025-10-10", "2025-10-10T00:00:00", "2025-10-10T02:00:00"),
    ("2025-10-10", "2025-10-10T10:00:00", "2025-10-10T15:00:00"),
)
COINS = ("BTC", "ETH")
FIVE_MIN_MS = 5 * 60_000
MINUTE_MS = 60_000
HALF_HOUR_MS = 30 * MINUTE_MS
PROXY_WINDOW_MS = 10_000


def epoch_ms(value: datetime) -> int:
    return int(value.replace(tzinfo=UTC).timestamp() * 1000)


def segment_ms() -> list[tuple[str, int, int]]:
    return [
        (date, epoch_ms(datetime.fromisoformat(start)), epoch_ms(datetime.fromisoformat(end)))
        for date, start, end in SEGMENTS
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_source(
    path: Path,
    date: str,
    segments: list[tuple[str, int, int]],
    flow: dict[tuple[str, int], float],
    trades: dict[str, list[tuple[int, float, float]]],
) -> dict[str, int]:
    actual_sha = sha256(path)
    if actual_sha != SOURCES[date]:
        raise ValueError(f"{date} source SHA-256 mismatch: {actual_sha}")
    connection = duckdb.connect()
    cursor = connection.execute(
        "SELECT block_number, block_time, local_time, events FROM read_parquet(?) "
        "ORDER BY block_number",
        [str(path)],
    )
    coverage: dict[str, list[int | None]] = {
        f"{start}:{end}": [None, None, None] for d, start, end in segments if d == date
    }
    seen_trades: set[tuple[int, str, int]] = set()
    counts: collections.Counter[str] = collections.Counter()
    while rows := cursor.fetchmany(256):
        for block_number, block_time, local_time, events_json in rows:
            block_ms = epoch_ms(block_time)
            local_ms = epoch_ms(local_time)
            chosen = next(
                (
                    (start, end)
                    for d, start, end in segments
                    if d == date and start <= block_ms < end
                ),
                None,
            )
            if chosen is None:
                continue
            start, end = chosen
            key = f"{start}:{end}"
            first, last, previous = coverage[key]
            if previous is not None and block_number != previous + 1:
                raise ValueError(f"block sequence gap inside {date} segment {key}")
            coverage[key] = [block_ms if first is None else first, block_ms, block_number]
            counts["blocks_in_fixed_segments"] += 1
            for wallet, fill in json.loads(events_json):
                coin = fill.get("coin")
                if coin not in COINS:
                    continue
                if not wallet:
                    raise ValueError("selected fill has no wallet")
                counts["selected_fill_rows"] += 1
                for field in ("tid", "time", "side", "px", "sz", "closedPnl", "crossed", "dir"):
                    if field not in fill:
                        raise ValueError(f"selected fill missing {field}")
                px = float(fill["px"])
                size = float(fill["sz"])
                if px <= 0 or size <= 0:
                    raise ValueError("nonpositive selected price or size")
                if fill["crossed"] is not True:
                    continue
                trade_key = (block_number, coin, int(fill["tid"]))
                if trade_key in seen_trades:
                    raise ValueError(f"duplicate selected taker trade: {trade_key}")
                seen_trades.add(trade_key)
                trade_ms = int(fill["time"])
                if abs(trade_ms - block_ms) > 1000:
                    raise ValueError("fill time differs from block time by over one second")
                trades[coin].append((trade_ms, px, size))
                counts["unique_selected_trades"] += 1
                direction = fill["dir"]
                if (
                    direction not in ("Close Long", "Close Short")
                    or float(fill["closedPnl"]) >= 0
                    or fill.get("liquidation") is not None
                ):
                    continue
                side = fill["side"]
                if (direction == "Close Long" and side != "A") or (
                    direction == "Close Short" and side != "B"
                ):
                    raise ValueError(
                        f"unexpected qualifying close side/direction: {side}/{direction}"
                    )
                counts["qualifying_taker_closes"] += 1
                bin_start = block_ms // FIVE_MIN_MS * FIVE_MIN_MS
                if local_ms > bin_start + FIVE_MIN_MS + MINUTE_MS:
                    counts["late_qualifying_closes_excluded"] += 1
                    continue
                flow[(coin, bin_start)] += (1 if side == "A" else -1) * px * size
    for key, (first, last, _) in coverage.items():
        start, end = (int(value) for value in key.split(":"))
        if first is None or first > start + 1000 or last is None or last < end - 1000:
            raise ValueError(f"source does not fully cover fixed segment {date} {key}")
    connection.close()
    return dict(counts)


def vwap(rows: list[tuple[int, float, float]], times: list[int], start_ms: int) -> float | None:
    left = bisect.bisect_left(times, start_ms)
    right = bisect.bisect_left(times, start_ms + PROXY_WINDOW_MS)
    if left == right:
        return None
    notional = sum(px * size for _, px, size in rows[left:right])
    size = sum(size for _, _, size in rows[left:right])
    return notional / size


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def median(values: list[float]) -> float:
    values = sorted(values)
    midpoint = len(values) // 2
    return values[midpoint] if len(values) % 2 else (values[midpoint - 1] + values[midpoint]) / 2


def summarize(events: list[dict[str, object]]) -> dict[str, float | int | None]:
    if not events:
        return {
            "n": 0,
            "gross_mean_bp": None,
            "gross_median_bp": None,
            "always_long_mean_bp": None,
            "always_short_mean_bp": None,
            "base_fee_floor_mean_bp": None,
            "ten_bp_per_side_mean_bp": None,
        }
    gross = [float(event["gross_bp"]) for event in events]
    long = [float(event["long_bp"]) for event in events]
    short = [-value for value in long]
    return {
        "n": len(events),
        "gross_mean_bp": mean(gross),
        "gross_median_bp": median(gross),
        "always_long_mean_bp": mean(long),
        "always_short_mean_bp": mean(short),
        "base_fee_floor_mean_bp": mean(gross) - 9,
        "ten_bp_per_side_mean_bp": mean(gross) - 20,
    }


def hour_block_interval(events: list[dict[str, object]]) -> list[float]:
    if not events:
        return []
    by_hour: dict[tuple[str, int], list[float]] = collections.defaultdict(list)
    for event in events:
        by_hour[(str(event["date"]), int(event["start_ms"]) // 3_600_000)].append(
            float(event["gross_bp"])
        )
    groups = list(by_hour.values())
    rng = random.Random(20260924)
    samples = []
    for _ in range(10_000):
        chosen = [rng.choice(groups) for _ in groups]
        values = [value for group in chosen for value in group]
        samples.append(mean(values))
    samples.sort()
    return [samples[250], samples[9750]]


def score(july: Path, october: Path) -> dict[str, object]:
    segments = segment_ms()
    flow: dict[tuple[str, int], float] = collections.defaultdict(float)
    trades: dict[str, list[tuple[int, float, float]]] = collections.defaultdict(list)
    source_counts = {
        "2025-07-28": load_source(july, "2025-07-28", segments, flow, trades),
        "2025-10-10": load_source(october, "2025-10-10", segments, flow, trades),
    }
    times: dict[str, list[int]] = {}
    for coin in COINS:
        trades[coin].sort(key=lambda row: row[0])
        times[coin] = [row[0] for row in trades[coin]]

    events: list[dict[str, object]] = []
    schedule = collections.Counter()
    signs = collections.Counter()
    for date, start, end in segments:
        t = start
        while t + FIVE_MIN_MS + MINUTE_MS + HALF_HOUR_MS + PROXY_WINDOW_MS <= end:
            for coin in COINS:
                schedule["scheduled"] += 1
                signed_notional = flow[(coin, t)]
                if signed_notional == 0:
                    schedule["cash_no_net_flow"] += 1
                    continue
                direction = 1 if signed_notional > 0 else -1
                entry_ms = t + FIVE_MIN_MS + MINUTE_MS
                exit_ms = entry_ms + HALF_HOUR_MS
                entry = vwap(trades[coin], times[coin], entry_ms)
                exit_price = vwap(trades[coin], times[coin], exit_ms)
                if entry is None or exit_price is None:
                    schedule["cash_missing_price_proxy"] += 1
                    continue
                price_return_bp = 10_000 * (exit_price / entry - 1)
                event = {
                    "date": date,
                    "coin": coin,
                    "start_ms": t,
                    "direction": direction,
                    "gross_bp": direction * price_return_bp,
                    "long_bp": price_return_bp,
                }
                events.append(event)
                schedule["active"] += 1
                signs[(date, coin, "long" if direction == 1 else "short")] += 1
            t += FIVE_MIN_MS

    by_date = {date: summarize([e for e in events if e["date"] == date]) for date in SOURCES}
    by_coin_date = {
        f"{date}/{coin}": summarize([e for e in events if e["date"] == date and e["coin"] == coin])
        for date in SOURCES
        for coin in COINS
    }
    total = summarize(events)
    sample_pass = all(by_date[date]["n"] >= 50 for date in SOURCES) and total["n"] >= 150
    gross_pass = sample_pass and all(
        by_date[date]["gross_mean_bp"] > 9
        and by_date[date]["gross_mean_bp"] > by_date[date]["always_long_mean_bp"]
        and by_date[date]["gross_mean_bp"] > by_date[date]["always_short_mean_bp"]
        for date in SOURCES
    )
    status = (
        "NO_SAMPLE"
        if not sample_pass
        else "GROSS_OR_FEE_FLOOR_FAILED"
        if not gross_pass
        else "CHEAP_GROSS_GATE_PASSED_NEEDS_SOURCE_AND_EXECUTION_VALIDATION"
    )
    return {
        "status": status,
        "source_sha256": {"2025-07-28": SOURCES["2025-07-28"], "2025-10-10": SOURCES["2025-10-10"]},
        "source_counts": source_counts,
        "scheduled_counts": dict(schedule),
        "direction_counts": {"/".join(key): value for key, value in sorted(signs.items())},
        "by_date": by_date,
        "by_coin_date": by_coin_date,
        "pooled": total,
        "pooled_hour_block_95pct_bp": hour_block_interval(events),
        "sample_gate_pass": sample_pass,
        "gross_and_control_gate_pass": gross_pass if sample_pass else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("july_parquet", type=Path)
    parser.add_argument("october_parquet", type=Path)
    args = parser.parse_args()
    print(json.dumps(score(args.july_parquet, args.october_parquet), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
