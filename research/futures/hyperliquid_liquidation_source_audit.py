"""Return-free structural audit of liquidation markers in a block-fill shard.

Requires DuckDB. Counts trades and event bins but never reads a future price
or calculates a conditioned return. The two wallet-fill rows for a trade are
checked together before counting one liquidation event.
"""

from __future__ import annotations

import argparse
import collections
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import duckdb


COINS = {"BTC", "ETH", "HYPE"}
FIVE_MINUTES_MS = 300_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def epoch_ms(value: datetime) -> int:
    return int(value.replace(tzinfo=UTC).timestamp() * 1000)


def audit(paths: list[Path]) -> dict[str, object]:
    connection = duckdb.connect()
    cursor = connection.execute(
        "SELECT block_number, block_time, local_time, events, _src "
        "FROM read_parquet(?) ORDER BY block_number",
        [[str(path) for path in paths]],
    )
    counts: collections.Counter[str] = collections.Counter()
    source_paths: collections.Counter[str] = collections.Counter()
    trade_counts: collections.Counter[tuple[str, str]] = collections.Counter()
    fill_counts: collections.Counter[tuple[str, str]] = collections.Counter()
    direction_counts: collections.Counter[tuple[str, str, str]] = collections.Counter()
    event_bins: collections.Counter[tuple[str, str, int]] = collections.Counter()
    actor_orders: set[tuple[str, str, str, int]] = set()
    actor_wallets: set[tuple[str, str, str]] = set()
    first_time: str | None = None
    last_time: str | None = None
    previous_block: int | None = None
    gaps: list[dict[str, int]] = []

    while rows := cursor.fetchmany(256):
        for block_number, block_time, local_time, events_json, source in rows:
            if first_time is None:
                first_time = block_time.isoformat()
            if previous_block is not None and block_number != previous_block + 1:
                gaps.append({"after": previous_block, "before": block_number})
            previous_block = block_number
            last_time = block_time.isoformat()
            source_paths[source] += 1
            counts["blocks"] += 1
            block_ms = epoch_ms(block_time)
            local_ms = epoch_ms(local_time)
            pairs: dict[tuple[str, int], list[tuple[str, dict[str, object]]]] = (
                collections.defaultdict(list)
            )
            for wallet, fill in json.loads(events_json):
                coin = fill.get("coin")
                if coin not in COINS:
                    continue
                if not wallet or "tid" not in fill:
                    counts["selected_missing_wallet_or_tid"] += 1
                    continue
                pairs[(str(coin), int(fill["tid"]))].append((wallet, fill))
            for (coin, _), pair in pairs.items():
                if len(pair) != 2:
                    counts["selected_unpaired_trade_keys"] += 1
                    continue
                marked = [(wallet, fill) for wallet, fill in pair if fill.get("liquidation")]
                if not marked:
                    continue
                counts["marked_trade_keys"] += 1
                if len(marked) != 2:
                    counts["one_sided_marker_trade_keys"] += 1
                    continue
                first_marker = marked[0][1]["liquidation"]
                second_marker = marked[1][1]["liquidation"]
                if first_marker != second_marker:
                    counts["marker_disagreement_trade_keys"] += 1
                    continue
                if not isinstance(first_marker, dict):
                    counts["invalid_marker_trade_keys"] += 1
                    continue
                method = first_marker.get("method", "MISSING")
                liquidated_user = first_marker.get("liquidatedUser")
                if not liquidated_user or first_marker.get("markPx") is None:
                    counts["missing_marker_field_trade_keys"] += 1
                fill_counts[(coin, str(method))] += 2
                trade_counts[(coin, str(method))] += 1
                takers = [(wallet, fill) for wallet, fill in pair if fill.get("crossed") is True]
                if len(takers) != 1:
                    counts["not_one_taker_trade_keys"] += 1
                    continue
                taker_wallet, taker_fill = takers[0]
                if taker_wallet != liquidated_user:
                    counts["taker_not_liquidated_user_trade_keys"] += 1
                if taker_fill.get("dir") not in ("Close Long", "Close Short"):
                    counts["taker_not_close_trade_keys"] += 1
                if float(taker_fill.get("closedPnl", "0")) >= 0:
                    counts["taker_nonnegative_closed_pnl_trade_keys"] += 1
                direction_counts[(coin, str(method), str(taker_fill.get("dir")))] += 1
                event_bins[(coin, str(method), block_ms // FIVE_MINUTES_MS)] += 1
                actor_orders.add((coin, str(method), taker_wallet, int(taker_fill.get("oid", -1))))
                actor_wallets.add((coin, str(method), taker_wallet))
                if local_ms > block_ms + 60_000:
                    counts["marked_trades_block_received_over_60s_late"] += 1
    connection.close()

    def by_coin_method(counter: collections.Counter[tuple[str, str]]) -> dict[str, int]:
        return {"/".join(key): value for key, value in sorted(counter.items())}

    bins = collections.Counter((coin, method) for coin, method, _ in event_bins)
    half_hour_bins = collections.Counter(
        (coin, method, five_minute_bin // 6)
        for coin, method, five_minute_bin in event_bins
    )
    half_hours = collections.Counter(
        (coin, method) for coin, method, _ in half_hour_bins
    )
    top_bins = sorted(event_bins.items(), key=lambda row: (-row[1], row[0]))[:12]
    return {
        "paths": [str(path) for path in paths],
        "source_sha256": {path.name: sha256(path) for path in paths},
        "first_block_time": first_time,
        "last_block_time": last_time,
        "counts": dict(counts),
        "block_gaps": gaps,
        "source_paths": dict(sorted(source_paths.items())),
        "marked_fill_rows_by_coin_method": by_coin_method(fill_counts),
        "marked_trades_by_coin_method": by_coin_method(trade_counts),
        "five_minute_bins_by_coin_method": by_coin_method(bins),
        "five_minute_bins_any_coin": len({key[2] for key in event_bins}),
        "thirty_minute_bins_by_coin_method": by_coin_method(half_hours),
        "thirty_minute_bins_any_coin": len({key[2] for key in half_hour_bins}),
        "top_five_minute_bins": [
            {
                "coin": coin,
                "method": method,
                "utc_start": datetime.fromtimestamp(
                    five_minute_bin * FIVE_MINUTES_MS / 1000, tz=UTC
                ).isoformat(),
                "trades": value,
            }
            for (coin, method, five_minute_bin), value in top_bins
        ],
        "distinct_liquidated_orders_by_coin_method": by_coin_method(
            collections.Counter((coin, method) for coin, method, _, _ in actor_orders)
        ),
        "distinct_liquidated_wallets_by_coin_method": by_coin_method(
            collections.Counter((coin, method) for coin, method, _ in actor_wallets)
        ),
        "taker_directions_by_coin_method": {
            "/".join(key): value for key, value in sorted(direction_counts.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parquet", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.parquet), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
