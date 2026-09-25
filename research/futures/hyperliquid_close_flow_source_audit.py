"""Return-free structural audit of a Hyperliquid block-fill Parquet shard.

Requires DuckDB (`pip install duckdb`). This script does not calculate prices
after any fill, strategy signals, or returns. It streams block envelopes to
avoid exploding every JSON field in a single database query.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

import duckdb


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(sorted_values: list[float], fraction: float) -> float:
    return sorted_values[min(int(len(sorted_values) * fraction), len(sorted_values) - 1)]


def audit(path: Path, coins: set[str]) -> dict[str, object]:
    connection = duckdb.connect()
    cursor = connection.execute(
        "SELECT block_number, block_time, local_time, events, _src "
        "FROM read_parquet(?) ORDER BY block_number",
        [str(path)],
    )
    counts: collections.Counter[str] = collections.Counter()
    per_coin: collections.Counter[str] = collections.Counter()
    per_source: collections.Counter[str] = collections.Counter()
    directions: collections.Counter[str] = collections.Counter()
    missing: collections.Counter[str] = collections.Counter()
    trade_multiplicity: collections.Counter[tuple[int, str, str]] = collections.Counter()
    seen_fills: set[tuple[int, str, str, str]] = set()
    lags_ms: list[float] = []
    first_block: int | None = None
    previous_block: int | None = None
    first_time: str | None = None
    last_time: str | None = None

    while rows := cursor.fetchmany(256):
        for block_number, block_time, local_time, events_json, source in rows:
            if first_block is None:
                first_block = block_number
                first_time = block_time.isoformat()
            if previous_block is not None and block_number != previous_block + 1:
                counts["block_sequence_gaps_or_duplicates"] += 1
            previous_block = block_number
            last_time = block_time.isoformat()
            per_source[source] += 1
            counts["blocks"] += 1
            lags_ms.append((local_time - block_time).total_seconds() * 1000)
            events = json.loads(events_json)
            counts["all_fill_rows"] += len(events)
            for wallet, fill in events:
                coin = fill.get("coin")
                if coin not in coins:
                    continue
                counts["selected_fill_rows"] += 1
                per_coin[coin] += 1
                directions[fill.get("dir", "MISSING")] += 1
                for field in ("tid", "closedPnl", "crossed", "time"):
                    if field not in fill:
                        missing[field] += 1
                if not wallet:
                    missing["wallet"] += 1
                tid = str(fill.get("tid"))
                key = (block_number, coin, tid, wallet)
                if key in seen_fills:
                    counts["duplicate_fill_keys"] += 1
                seen_fills.add(key)
                trade_multiplicity[(block_number, coin, tid)] += 1
                liquidation = fill.get("liquidation")
                if liquidation is not None:
                    counts["marked_liquidation_fills"] += 1
                if (
                    fill.get("crossed") is True
                    and fill.get("dir", "").startswith("Close")
                    and float(fill.get("closedPnl", "0")) < 0
                ):
                    counts["loss_realizing_taker_closes"] += 1
                    if liquidation is None:
                        counts["unmarked_loss_realizing_taker_closes"] += 1
                    else:
                        counts["marked_loss_realizing_taker_closes"] += 1

    if not lags_ms:
        raise ValueError("Parquet shard has no blocks")
    lags_ms.sort()
    result = {
        "path": str(path),
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
        "coins": sorted(coins),
        "first_block": first_block,
        "last_block": previous_block,
        "first_block_time": first_time,
        "last_block_time": last_time,
        "counts": dict(counts),
        "fills_by_coin": dict(per_coin),
        "directions": dict(directions),
        "missing_required_fields": dict(missing),
        "trade_id_multiplicity": dict(collections.Counter(trade_multiplicity.values())),
        "blocks_by_original_source": dict(sorted(per_source.items())),
        "local_minus_block_time_ms": {
            "min": lags_ms[0],
            "median": percentile(lags_ms, 0.5),
            "p95": percentile(lags_ms, 0.95),
            "p99": percentile(lags_ms, 0.99),
            "max": lags_ms[-1],
        },
    }
    connection.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parquet", type=Path)
    parser.add_argument("--coins", nargs="+", default=["BTC", "ETH"])
    args = parser.parse_args()
    print(json.dumps(audit(args.parquet, set(args.coins)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
