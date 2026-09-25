"""Score frozen FUT-012 using only SHA-pinned complete-day HYPE fills."""

from __future__ import annotations

import argparse
import collections
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import duckdb

from fut011_score import hour_block_interval, summarize, vwap


FIVE_MIN_MS = 300_000
THIRTY_MIN_MS = 1_800_000
ENTRY_MS = 360_000
HOLD_MS = 7_200_000
PROXY_MS = 10_000
DATES = ("20250814", "20250918", "20250925", "20251004")


def timestamp_ms(value: datetime) -> int:
    return int(value.replace(tzinfo=UTC).timestamp() * 1000)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_date(paths: list[Path], date: str) -> tuple[dict[int, float], list[tuple[int, float, float]], dict[str, int]]:
    flow: dict[int, float] = collections.defaultdict(float)
    trades: list[tuple[int, float, float]] = []
    counts: collections.Counter[str] = collections.Counter()
    connection = duckdb.connect()
    cursor = connection.execute(
        "SELECT block_number, block_time, local_time, events FROM read_parquet(?) ORDER BY block_number",
        [[str(path) for path in paths]],
    )
    previous: int | None = None
    day_start = timestamp_ms(datetime.strptime(date, "%Y%m%d"))
    day_end = day_start + 86_400_000
    first_ms: int | None = None
    last_ms: int | None = None
    while rows := cursor.fetchmany(256):
        for block_number, block_time, local_time, events_json in rows:
            block_ms = timestamp_ms(block_time)
            local_ms = timestamp_ms(local_time)
            if previous is not None and block_number != previous + 1:
                raise ValueError(f"{date}: nonconsecutive block after {previous}")
            previous = block_number
            first_ms = block_ms if first_ms is None else first_ms
            last_ms = block_ms
            counts["blocks"] += 1
            if not day_start <= block_ms < day_end:
                continue
            pairs: dict[int, list[tuple[str, dict[str, object]]]] = collections.defaultdict(list)
            for wallet, fill in json.loads(events_json):
                if fill.get("coin") == "HYPE":
                    if not wallet or "tid" not in fill:
                        raise ValueError("HYPE fill missing wallet/tid")
                    pairs[int(fill["tid"])].append((wallet, fill))
            for tid, pair in pairs.items():
                if len(pair) != 2:
                    raise ValueError(f"{date}: unpaired HYPE trade {block_number}/{tid}")
                takers = [(wallet, fill) for wallet, fill in pair if fill.get("crossed") is True]
                if len(takers) != 1:
                    raise ValueError(f"{date}: invalid HYPE taker count {block_number}/{tid}")
                wallet, taker = takers[0]
                for field in ("time", "px", "sz", "side", "dir"):
                    if field not in taker:
                        raise ValueError(f"HYPE taker missing {field}")
                trade_ms = int(taker["time"])
                px = float(taker["px"])
                size = float(taker["sz"])
                if px <= 0 or size <= 0 or abs(trade_ms - block_ms) > 1000:
                    raise ValueError("HYPE trade invalid price, size, or clock")
                trades.append((trade_ms, px, size))
                counts["hype_trades"] += 1
                marker = taker.get("liquidation")
                if marker is None:
                    continue
                if marker != pair[0][1].get("liquidation") or marker != pair[1][1].get("liquidation"):
                    raise ValueError("HYPE liquidation marker mismatch")
                if not isinstance(marker, dict) or not marker.get("liquidatedUser") or marker.get("markPx") is None:
                    raise ValueError("invalid HYPE liquidation marker")
                if marker.get("method") != "market":
                    counts["backstop_excluded"] += 1
                    continue
                if wallet != marker["liquidatedUser"]:
                    raise ValueError("market liquidation taker is not liquidated user")
                direction = taker["dir"]
                side = taker["side"]
                if (direction, side) not in (("Close Long", "A"), ("Close Short", "B")):
                    raise ValueError(f"invalid market liquidation side {direction}/{side}")
                counts["market_liquidation_trades"] += 1
                bin_start = block_ms // FIVE_MIN_MS * FIVE_MIN_MS
                if local_ms > bin_start + ENTRY_MS:
                    counts["late_liquidation_excluded"] += 1
                    continue
                flow[bin_start] += (1 if side == "A" else -1) * px * size
    connection.close()
    if first_ms is None or first_ms > day_start or last_ms is None or last_ms < day_end - 1000:
        raise ValueError(f"{date}: incomplete day coverage")
    trades.sort(key=lambda row: row[0])
    return flow, trades, dict(counts)


def score(manifest_path: Path, root: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text())
    if tuple(manifest["dates"]) != DATES:
        raise ValueError("source dates differ from frozen contract")
    by_date: dict[str, dict[str, object]] = {}
    events: list[dict[str, object]] = []
    source_counts: dict[str, dict[str, int]] = {}
    source_sha256: dict[str, str] = {}
    disposition: dict[str, dict[str, int]] = {}
    directions: dict[str, dict[str, int]] = {}
    for date in DATES:
        sources = manifest["dates"][date]
        if len(sources) != 24 or [item["hour_suffix"] for item in sources] != list(range(24)):
            raise ValueError(f"{date}: not exactly 24 ordered hourly shards")
        paths = [root / date / item["filename"] for item in sources]
        for path, item in zip(paths, sources, strict=True):
            if path.stat().st_size != item["size_bytes"] or sha256(path) != item["sha256"]:
                raise ValueError(f"source hash or size mismatch: {path}")
            source_sha256[item["filename"]] = item["sha256"]
        flow, trades, source_counts[date] = read_date(paths, date)
        times = [row[0] for row in trades]
        day_start = timestamp_ms(datetime.strptime(date, "%Y%m%d"))
        day_end = day_start + 86_400_000
        eligible = sorted(t for t in flow if day_start <= t and t + ENTRY_MS + HOLD_MS + PROXY_MS <= day_end)
        retained = []
        for t in eligible:
            if not retained or t >= retained[-1] + THIRTY_MIN_MS:
                retained.append(t)
        if len(retained) != {"20250814": 16, "20250918": 6, "20250925": 23, "20251004": 9}[date]:
            raise ValueError(f"{date}: eligible episode count changed: {len(retained)}")
        cash = collections.Counter()
        signs = collections.Counter()
        date_events = []
        for t in retained:
            signed = flow[t]
            if signed == 0:
                cash["zero_signed_notional"] += 1
                continue
            entry = vwap(trades, times, t + ENTRY_MS)
            exit_price = vwap(trades, times, t + ENTRY_MS + HOLD_MS)
            if entry is None or exit_price is None:
                cash["missing_trade_proxy"] += 1
                continue
            direction = 1 if signed > 0 else -1
            long_bp = 10_000 * (exit_price / entry - 1)
            event = {"date": date, "start_ms": t, "direction": direction,
                     "gross_bp": direction * long_bp, "long_bp": long_bp}
            date_events.append(event)
            signs["long" if direction == 1 else "short"] += 1
        events.extend(date_events)
        disposition[date] = {"source_eligible": len(retained), "active": len(date_events), **dict(cash)}
        directions[date] = dict(signs)
        by_date[date] = summarize(date_events)
    halves = {
        "A_20250814_20250918": summarize([e for e in events if e["date"] in DATES[:2]]),
        "B_20250925_20251004": summarize([e for e in events if e["date"] in DATES[2:]]),
    }
    pooled = summarize(events)
    sample_pass = pooled["n"] >= 40 and all(by_date[date]["n"] >= 5 for date in DATES)
    gross_pass = sample_pass and all(
        row["gross_mean_bp"] > 9
        and row["gross_mean_bp"] > row["always_long_mean_bp"]
        and row["gross_mean_bp"] > row["always_short_mean_bp"]
        for row in halves.values()
    )
    status = ("NO_SAMPLE" if not sample_pass else
              "CHEAP_GROSS_GATE_PASSED_NEEDS_SOURCE_AND_EXECUTION_VALIDATION" if gross_pass else
              "GROSS_OR_INCREMENTAL_FEE_FLOOR_FAILED")
    return {"status": status, "source_sha256": source_sha256, "source_counts": source_counts,
            "disposition": disposition, "direction_counts": directions, "by_date": by_date,
            "chronological_halves": halves, "pooled": pooled,
            "pooled_hour_block_95pct_bp": hour_block_interval(events),
            "sample_gate_pass": sample_pass,
            "gross_and_control_gate_pass": gross_pass if sample_pass else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("root", type=Path, help="directory with YYYYMMDD child directories")
    args = parser.parse_args()
    print(json.dumps(score(args.manifest, args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
