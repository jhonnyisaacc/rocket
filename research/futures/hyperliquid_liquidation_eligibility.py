"""Return-free count of delayed 120-minute liquidation-event opportunities.

Requires DuckDB. This reads liquidation markers and source clocks only; it
does not access post-event prices, construct a trading signal, or score P&L.
Use after the paired-fill structural auditor has validated each shard.
"""

from __future__ import annotations

import argparse
import collections
from datetime import UTC, datetime
import json
from pathlib import Path

import duckdb


COINS = {"BTC", "ETH", "HYPE"}
FIVE_MINUTES_MS = 300_000
THIRTY_MINUTES_MS = 1_800_000
ENTRY_DELAY_MS = 6 * 60_000
HOLD_MS = 120 * 60_000
PROXY_MS = 10_000


def epoch_ms(value: datetime) -> int:
    return int(value.replace(tzinfo=UTC).timestamp() * 1000)


def rounded_segment_bounds(first_ms: int, last_ms: int) -> tuple[int, int]:
    start = (first_ms + FIVE_MINUTES_MS - 1) // FIVE_MINUTES_MS * FIVE_MINUTES_MS
    end = (last_ms + 1000) // FIVE_MINUTES_MS * FIVE_MINUTES_MS
    return start, end


def spaced_count(times: list[int]) -> int:
    count = 0
    last_selected: int | None = None
    for time in sorted(set(times)):
        if last_selected is None or time >= last_selected + THIRTY_MINUTES_MS:
            count += 1
            last_selected = time
    return count


def audit(path: Path) -> dict[str, object]:
    connection = duckdb.connect()
    cursor = connection.execute(
        "SELECT block_number, block_time, events FROM read_parquet(?) ORDER BY block_number",
        [str(path)],
    )
    segments: list[dict[str, object]] = []
    previous_block: int | None = None
    current: dict[str, object] | None = None
    while rows := cursor.fetchmany(256):
        for block_number, block_time, events_json in rows:
            block_ms = epoch_ms(block_time)
            if previous_block is None or block_number != previous_block + 1:
                if current is not None:
                    segments.append(current)
                current = {"first_ms": block_ms, "last_ms": block_ms, "bins": set()}
            assert current is not None
            current["last_ms"] = block_ms
            previous_block = block_number
            for wallet, fill in json.loads(events_json):
                if fill.get("coin") not in COINS or fill.get("crossed") is not True:
                    continue
                marker = fill.get("liquidation")
                if not marker or marker.get("method") != "market":
                    continue
                if marker.get("liquidatedUser") != wallet:
                    raise ValueError("marked taker is not the liquidated wallet")
                current["bins"].add((fill["coin"], block_ms // FIVE_MINUTES_MS * FIVE_MINUTES_MS))
    if current is not None:
        segments.append(current)
    connection.close()

    by_coin_raw: collections.Counter[str] = collections.Counter()
    by_coin_eligible: collections.Counter[str] = collections.Counter()
    eligible_by_coin: dict[str, set[int]] = collections.defaultdict(set)
    segment_rows: list[dict[str, object]] = []
    all_raw: set[int] = set()
    all_eligible: set[int] = set()
    for segment in segments:
        first_ms = int(segment["first_ms"])
        last_ms = int(segment["last_ms"])
        start, end = rounded_segment_bounds(first_ms, last_ms)
        raw_bins = set(segment["bins"])
        eligible_bins = {
            (coin, time)
            for coin, time in raw_bins
            if time >= start and time + ENTRY_DELAY_MS + HOLD_MS + PROXY_MS <= end
        }
        for coin in COINS:
            raw = [time for c, time in raw_bins if c == coin]
            eligible = [time for c, time in eligible_bins if c == coin]
            by_coin_raw[coin] += len(raw)
            by_coin_eligible[coin] += len(eligible)
            eligible_by_coin[coin].update(eligible)
        raw_times = {time for _, time in raw_bins}
        eligible_times = {time for _, time in eligible_bins}
        all_raw.update(raw_times)
        all_eligible.update(eligible_times)
        segment_rows.append(
            {
                "source_start": datetime.fromtimestamp(first_ms / 1000, tz=UTC).isoformat(),
                "source_end": datetime.fromtimestamp(last_ms / 1000, tz=UTC).isoformat(),
                "full_bin_start": datetime.fromtimestamp(start / 1000, tz=UTC).isoformat(),
                "full_bin_end": datetime.fromtimestamp(end / 1000, tz=UTC).isoformat(),
                "market_wide_raw_five_minute_bins": len(raw_times),
                "market_wide_eligible_five_minute_bins": len(eligible_times),
                "market_wide_eligible_spaced_episodes": spaced_count(list(eligible_times)),
            }
        )
    return {
        "path": str(path),
        "segments": segment_rows,
        "raw_five_minute_bins_by_coin": dict(sorted(by_coin_raw.items())),
        "eligible_five_minute_bins_by_coin": dict(sorted(by_coin_eligible.items())),
        "eligible_spaced_episodes_by_coin": {
            coin: spaced_count(list(eligible_by_coin[coin])) for coin in sorted(COINS)
        },
        "market_wide_raw_five_minute_bins": len(all_raw),
        "market_wide_eligible_five_minute_bins": len(all_eligible),
        "market_wide_eligible_spaced_episodes": spaced_count(list(all_eligible)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parquet", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.parquet), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
