"""Stream-audit an official OKX daily L2 archive without reading strategy returns.

The public archive has no sequence number or checksum manifest. Timestamp and
book checks can expose obvious defects but cannot certify lossless updates.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def audit(path: Path, day: dt.date) -> dict:
    start = int(dt.datetime.combine(day, dt.time(), dt.timezone.utc).timestamp() * 1000)
    end = start + 86_400_000
    expected_member = path.name.removesuffix(".tar.gz") + ".data"
    digest = digest_file(path)
    counts = {"snapshot": 0, "update": 0}
    hours = [0] * 24
    minutes = set()
    bids: dict[float, float] = {}
    asks: dict[float, float] = {}
    first_ms = last_ms = previous_ms = None
    max_gap_ms = gap_over_1s = gap_over_10s = duplicate_ts = 0
    out_of_order = invalid_levels = crossed_checks = empty_checks = 0
    minute_checks = 0
    first_bid_size = first_spread_bps = None
    max_bid_levels = max_ask_levels = 0
    rows = blank_rows = 0

    with tarfile.open(path, "r|gz") as archive:
        members = iter(archive)
        member = next(members, None)
        if member is None or member.name != expected_member or not member.isfile():
            raise ValueError(f"unexpected archive member: {member}")
        stream = archive.extractfile(member)
        if stream is None:
            raise ValueError("archive member cannot be read")
        for raw in stream:
            if not raw.strip():
                blank_rows += 1
                continue
            row = json.loads(raw)
            if row.get("instId") != "BTC-USDT-SWAP":
                raise ValueError(f"unexpected instrument: {row.get('instId')}")
            action = row.get("action")
            if action not in counts:
                raise ValueError(f"unexpected action: {action}")
            stamp = int(row["ts"])
            if not start <= stamp < end:
                raise ValueError(f"out-of-day timestamp: {stamp}")
            if previous_ms is not None:
                gap = stamp - previous_ms
                out_of_order += gap < 0
                duplicate_ts += gap == 0
                max_gap_ms = max(max_gap_ms, gap)
                gap_over_1s += gap > 1_000
                gap_over_10s += gap > 10_000
            if action == "snapshot":
                bids.clear()
                asks.clear()
            for name, book in (("bids", bids), ("asks", asks)):
                for level in row[name]:
                    if len(level) != 3:
                        raise ValueError(f"unexpected {name} level: {level}")
                    price, size = float(level[0]), float(level[1])
                    if price <= 0 or size < 0 or int(level[2]) < 0:
                        invalid_levels += 1
                    if size == 0:
                        book.pop(price, None)
                    else:
                        book[price] = size
            minute = (stamp - start) // 60_000
            if minute not in minutes:
                minute_checks += 1
                if not bids or not asks:
                    empty_checks += 1
                else:
                    best_bid, best_ask = max(bids), min(asks)
                    crossed_checks += best_bid >= best_ask
                    if first_bid_size is None:
                        first_bid_size = bids[best_bid]
                        first_spread_bps = (best_ask / best_bid - 1) * 10_000
            minutes.add(minute)
            hours[(stamp - start) // 3_600_000] += 1
            counts[action] += 1
            rows += 1
            first_ms = stamp if first_ms is None else first_ms
            last_ms = previous_ms = stamp
            max_bid_levels = max(max_bid_levels, len(bids))
            max_ask_levels = max(max_ask_levels, len(asks))
        if next(members, None) is not None:
            raise ValueError("unexpected additional archive member")

    return {
        "source_key": path.name,
        "sha256": digest,
        "compressed_bytes": path.stat().st_size,
        "scope": "one fixed UTC BTC-USDT-SWAP L2 day; no returns",
        "member": expected_member,
        "rows": rows,
        "blank_rows": blank_rows,
        "actions": counts,
        "first_ms": first_ms,
        "last_ms": last_ms,
        "distinct_minutes": len(minutes),
        "rows_by_utc_hour": hours,
        "out_of_order_pairs": out_of_order,
        "duplicate_timestamp_pairs": duplicate_ts,
        "maximum_timestamp_gap_ms": max_gap_ms,
        "gaps_over_1s": gap_over_1s,
        "gaps_over_10s": gap_over_10s,
        "invalid_levels": invalid_levels,
        "minute_book_checks": minute_checks,
        "empty_minute_book_checks": empty_checks,
        "crossed_minute_book_checks": crossed_checks,
        "maximum_bid_levels_reconstructed": max_bid_levels,
        "maximum_ask_levels_reconstructed": max_ask_levels,
        "first_best_bid_size_raw": first_bid_size,
        "first_spread_bps": first_spread_bps,
        "caveat": "No sequence numbers: apparent coverage cannot prove no dropped updates.",
    }


def audit_trades(paths: list[Path], day: dt.date) -> dict:
    """Check both UTC+8 trade files overlapping one UTC order-book day."""
    start = int(dt.datetime.combine(day, dt.time(), dt.timezone.utc).timestamp() * 1000)
    end = start + 86_400_000
    expected_columns = ("instrument_name", "trade_id", "side", "price", "size", "created_time")
    files = []
    minutes = set()
    previous_file_last_ts = previous_file_last_id = None
    for path in paths:
        rows = selected_rows = disorder = id_gaps = 0
        first_ms = last_ms = first_id = last_id = None
        previous_ms = previous_id = None
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if names != [path.stem + ".csv"]:
                raise ValueError(f"unexpected trade ZIP layout: {names}")
            with archive.open(names[0]) as handle:
                reader = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8"))
                if tuple(reader.fieldnames or ()) != expected_columns:
                    raise ValueError(f"unexpected trade columns: {reader.fieldnames}")
                for row in reader:
                    if row["instrument_name"] != "BTC-USDT-SWAP":
                        raise ValueError(f"unexpected trade instrument: {row['instrument_name']}")
                    stamp, trade_id = int(row["created_time"]), int(row["trade_id"])
                    if row["side"] not in ("buy", "sell") or float(row["price"]) <= 0 or float(row["size"]) <= 0:
                        raise ValueError("invalid trade side, price or size")
                    if previous_ms is not None:
                        disorder += stamp < previous_ms or trade_id <= previous_id
                        id_gaps += trade_id != previous_id + 1
                    if start <= stamp < end:
                        selected_rows += 1
                        minutes.add((stamp - start) // 60_000)
                    first_ms = stamp if first_ms is None else first_ms
                    first_id = trade_id if first_id is None else first_id
                    last_ms = previous_ms = stamp
                    last_id = previous_id = trade_id
                    rows += 1
        if previous_file_last_ts is not None:
            if first_ms <= previous_file_last_ts or first_id != previous_file_last_id + 1:
                raise ValueError("trade files overlap or have an ID gap")
        previous_file_last_ts, previous_file_last_id = last_ms, last_id
        files.append({"source_key": path.name, "sha256": digest_file(path),
                      "compressed_bytes": path.stat().st_size, "rows": rows,
                      "first_ms": first_ms, "last_ms": last_ms,
                      "first_trade_id": first_id, "last_trade_id": last_id,
                      "utc_day_rows": selected_rows,
                      "out_of_order_pairs": disorder,
                      "nonconsecutive_trade_id_pairs": id_gaps})
    return {"files": files, "utc_day_trade_rows": sum(f["utc_day_rows"] for f in files),
            "utc_day_distinct_trade_minutes": len(minutes)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--day", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--trade-archives", type=Path, nargs=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.archive, args.day)
    if args.trade_archives:
        report["trade_companion"] = audit_trades(args.trade_archives, args.day)
    output = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
