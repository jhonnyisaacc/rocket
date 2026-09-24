"""Score the frozen FUT-008 near-touch pressure pilot on two OKX source days."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import tarfile
import zipfile
from collections import Counter
from pathlib import Path

from research.futures.okx_l2_audit import digest_file

FROZEN = {
    "2023-04-01": {
        "l2": "cb38f07ba8f1770f6d91d9a7fbb020b9031b9888c7e7e2cf8dd438ce9a5e33fc",
        "trades": (
            "546e8365f4936056f697f1fc55ceabf92085577b74b74f22bfff987d07bae537",
            "868a704b822c7453c30dda526a7e4f3d81a8c419ab3ac5c16c914bc0962e3dae",
        ),
    },
    "2024-09-01": {
        "l2": "437a49aabe412423b2f7ea1d5bd6571eef7f019c108201ead01dca9b2610f788",
        "trades": (
            "89e5e30f8ecf7074b40e92eb2dcfe604012083402ec6c1220bc7ab240483fd44",
            "bddb2da7041465f912b232736f961a19847f05060058c67100391003d0f3edd3",
        ),
    },
}
FIVE_MIN_MS = 300_000
ONE_MIN_MS = 60_000
DELAY_MS = 10_000
MAX_STALE_MS = 1_000


def next_day(day: str) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat()


def start_ms(day: str) -> int:
    return int(dt.datetime.combine(
        dt.date.fromisoformat(day), dt.time(), dt.timezone.utc,
    ).timestamp() * 1000)


def check_digest(path: Path, expected: str) -> None:
    actual = digest_file(path)
    if actual != expected:
        raise ValueError(f"source hash mismatch: {path.name}: {actual}")


def trade_minutes(root: Path, day: str) -> tuple[list[float], list[float], dict]:
    """Return the complete UTC day's buy/sell taker-contract minute sums."""
    start, end = start_ms(day), start_ms(day) + 86_400_000
    buy, sell = [0.0] * 1440, [0.0] * 1440
    minute_counts = [0] * 1440
    prior_id = prior_ms = None
    file_rows = []
    for file_day, expected in zip((day, next_day(day)), FROZEN[day]["trades"]):
        path = root / f"BTC-USDT-SWAP-trades-{file_day}.zip"
        check_digest(path, expected)
        count = selected = 0
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if names != [path.stem + ".csv"]:
                raise ValueError(f"unexpected trade archive layout: {path.name}")
            with archive.open(names[0]) as handle:
                reader = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8"))
                if tuple(reader.fieldnames or ()) != (
                    "instrument_name", "trade_id", "side", "price", "size", "created_time"
                ):
                    raise ValueError(f"unexpected trade schema: {path.name}")
                for row in reader:
                    if row["instrument_name"] != "BTC-USDT-SWAP":
                        raise ValueError("unexpected trade instrument")
                    stamp, trade_id = int(row["created_time"]), int(row["trade_id"])
                    if prior_id is not None and (trade_id != prior_id + 1 or stamp < prior_ms):
                        raise ValueError("trade ID gap or timestamp disorder")
                    prior_id, prior_ms = trade_id, stamp
                    side, size = row["side"], float(row["size"])
                    if side not in ("buy", "sell") or size <= 0:
                        raise ValueError("invalid trade side or quantity")
                    if start <= stamp < end:
                        minute = (stamp - start) // ONE_MIN_MS
                        (buy if side == "buy" else sell)[minute] += size
                        minute_counts[minute] += 1
                        selected += 1
                    count += 1
        file_rows.append({"file": path.name, "rows": count, "utc_day_rows": selected})
    if not all(minute_counts):
        raise ValueError("missing trade minute in fixed UTC day")
    return buy, sell, {"files": file_rows, "utc_day_trade_rows": sum(minute_counts),
                       "distinct_trade_minutes": 1440}


def touch(bids: dict[float, float], asks: dict[float, float], stamp: int,
          target: int, age: int) -> dict | None:
    if age < 0 or age > MAX_STALE_MS or not bids or not asks:
        return None
    bid, ask = max(bids), min(asks)
    if bid <= 0 or bid >= ask or bids[bid] <= 0 or asks[ask] <= 0:
        return None
    return {"stamp": stamp, "target": target, "age_ms": age,
            "bid": bid, "ask": ask, "bid_size": bids[bid],
            "mid": (bid + ask) / 2}


def book_samples(path: Path, day: str) -> list[dict]:
    """Capture only frozen decision and delayed execution clocks."""
    start = start_ms(day)
    windows = [start + i * FIVE_MIN_MS for i in range(1, 287)]
    decisions = [(stamp, i) for i, stamp in enumerate(windows)]
    fills = sorted(
        [(stamp + DELAY_MS, "entry", i) for i, stamp in enumerate(windows)]
        + [(stamp + FIVE_MIN_MS + DELAY_MS, "exit", i)
           for i, stamp in enumerate(windows)]
    )
    samples = [{"decision_time": stamp} for stamp in windows]
    decision_index = fill_index = 0
    bids: dict[float, float] = {}
    asks: dict[float, float] = {}
    previous_ms = None
    rows = 0
    with tarfile.open(path, "r|gz") as archive:
        members = iter(archive)
        member = next(members, None)
        if member is None or member.name != path.name.removesuffix(".tar.gz") + ".data":
            raise ValueError("unexpected L2 archive member")
        stream = archive.extractfile(member)
        if stream is None:
            raise ValueError("unreadable L2 member")
        for raw in stream:
            row = json.loads(raw)
            if row.get("instId") != "BTC-USDT-SWAP":
                raise ValueError("unexpected book instrument")
            stamp = int(row["ts"])
            if not start <= stamp < start + 86_400_000 or (
                previous_ms is not None and stamp <= previous_ms
            ):
                raise ValueError("L2 timestamp outside day or not increasing")
            while decision_index < len(decisions) and decisions[decision_index][0] <= stamp:
                target, i = decisions[decision_index]
                samples[i]["decision"] = touch(
                    bids, asks, previous_ms if previous_ms is not None else -1,
                    target, target - previous_ms if previous_ms is not None else -1,
                )
                decision_index += 1
            if row["action"] == "snapshot":
                bids.clear()
                asks.clear()
            elif row["action"] != "update":
                raise ValueError("unexpected book action")
            for name, book in (("bids", bids), ("asks", asks)):
                for level in row[name]:
                    price, size = float(level[0]), float(level[1])
                    if size == 0:
                        book.pop(price, None)
                    elif price > 0 and size > 0:
                        book[price] = size
                    else:
                        raise ValueError("invalid book price/size")
            while fill_index < len(fills) and fills[fill_index][0] <= stamp:
                target, kind, i = fills[fill_index]
                samples[i][kind] = touch(bids, asks, stamp, target, stamp - target)
                fill_index += 1
            previous_ms = stamp
            rows += 1
        if next(members, None) is not None:
            raise ValueError("unexpected additional L2 member")
    if decision_index != len(decisions) or fill_index != len(fills):
        raise ValueError("missing end-of-day book capture")
    for sample in samples:
        for kind in ("decision", "entry", "exit"):
            if kind not in sample:
                raise ValueError(f"capture missing: {kind}")
    return samples


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def bps(value: float | None) -> float | None:
    return value * 10_000 if value is not None else None


def score_day(root: Path, day: str) -> dict:
    expected = FROZEN[day]
    l2_path = root / f"BTC-USDT-SWAP-L2orderbook-400lv-{day}.tar.gz"
    check_digest(l2_path, expected["l2"])
    buy, sell, trade_report = trade_minutes(root, day)
    samples = book_samples(l2_path, day)
    valid = []
    unresolved = Counter()
    for sample in samples:
        if any(sample[kind] is None for kind in ("decision", "entry", "exit")):
            unresolved["missing_or_stale_book"] += 1
            continue
        stamp = sample["decision_time"]
        minute = (stamp - start_ms(day)) // ONE_MIN_MS - 1
        net_sell = sell[minute] - buy[minute]
        capacity = sample["decision"]["bid_size"]
        if capacity <= 0:
            unresolved["missing_capacity"] += 1
            continue
        pressure = max(0.0, net_sell) / capacity
        entry, exit_ = sample["entry"], sample["exit"]
        mid_gross = (entry["mid"] - exit_["mid"]) / entry["mid"]
        executable_gross = (entry["bid"] - exit_["ask"]) / entry["bid"]
        valid.append({"T": stamp, "hour": (stamp - start_ms(day)) // 3_600_000,
                      "pressure": pressure, "net_sell_positive": net_sell > 0,
                      "trigger": pressure > 1,
                      "mid_gross": mid_gross, "executable_gross": executable_gross,
                      "decision_age_ms": sample["decision"]["age_ms"],
                      "entry_delay_ms": entry["age_ms"], "exit_delay_ms": exit_["age_ms"]})
    triggered = [row for row in valid if row["trigger"]]
    flow_only = [row for row in valid if row["net_sell_positive"]]
    subset = lambda rows, key: [row[key] for row in rows]
    trigger_mid = mean(subset(triggered, "mid_gross"))
    all_mid = mean(subset(valid, "mid_gross"))
    trigger_exec = mean(subset(triggered, "executable_gross"))
    run = max_run = 0
    for sample in samples:
        matched = next((r for r in valid if r["T"] == sample["decision_time"]), None)
        run = run + 1 if matched and matched["trigger"] else 0
        max_run = max(max_run, run)
    return {
        "day": day, "schedule_count": len(samples), "eligible_count": len(valid),
        "unresolved": dict(unresolved), "trade_source": trade_report,
        "trigger_count": len(triggered), "flow_only_count": len(flow_only),
        "trigger_hours": dict(sorted(Counter(r["hour"] for r in triggered).items())),
        "longest_consecutive_trigger_run": max_run,
        "mean_trigger_pressure": mean(subset(triggered, "pressure")),
        "max_trigger_pressure": max(subset(triggered, "pressure"), default=None),
        "max_decision_book_age_ms": max(subset(valid, "decision_age_ms"), default=None),
        "max_entry_capture_delay_ms": max(subset(valid, "entry_delay_ms"), default=None),
        "max_exit_capture_delay_ms": max(subset(valid, "exit_delay_ms"), default=None),
        "trigger_mid_gross_bps": bps(trigger_mid),
        "all_short_mid_gross_bps": bps(all_mid),
        "trigger_minus_all_mid_gross_bps": bps(
            trigger_mid - all_mid if trigger_mid is not None and all_mid is not None else None
        ),
        "flow_only_mid_gross_bps": bps(mean(subset(flow_only, "mid_gross"))),
        "trigger_touch_gross_bps": bps(trigger_exec),
        "trigger_touch_net_5bp_side_bps": bps(trigger_exec) - 10 if trigger_exec is not None else None,
        "trigger_touch_net_10bp_side_bps": bps(trigger_exec) - 20 if trigger_exec is not None else None,
        "all_short_touch_net_5bp_side_bps": bps(mean(subset(valid, "executable_gross"))) - 10 if valid else None,
        "flow_only_touch_net_5bp_side_bps": bps(mean(subset(flow_only, "executable_gross"))) - 10 if flow_only else None,
    }


def score(root: Path) -> dict:
    days = [score_day(root, day) for day in FROZEN]
    enough = all(day["trigger_count"] >= 20 for day in days)
    conditions = [
        day["trigger_mid_gross_bps"] is not None
        and day["trigger_mid_gross_bps"] > 0
        and day["trigger_minus_all_mid_gross_bps"] > 0
        and day["trigger_touch_net_5bp_side_bps"] > 0
        for day in days
    ]
    total_triggers = sum(day["trigger_count"] for day in days)
    combined_10bp = (
        sum(day["trigger_touch_net_10bp_side_bps"] * day["trigger_count"]
            for day in days) / total_triggers
        if total_triggers and all(day["trigger_touch_net_10bp_side_bps"] is not None for day in days)
        else None
    )
    passed = enough and all(conditions) and combined_10bp is not None and combined_10bp > 0
    return {"experiment": "FUT-008", "scope": "frozen two-day optimistic OKX pilot",
            "freeze_commit": "d77c052", "days": days,
            "combined_trigger_touch_net_10bp_side_bps": combined_10bp,
            "sample_gate": enough, "daily_economic_gates": conditions,
            "passed_all_frozen_gates": passed,
            "attribution": "PILOT_PASS_REQUIRES_BROADER_SOURCE" if passed else
                           "NO_SAMPLE" if not enough else "GROSS_OR_COST_GATE_FAILED",
            "caveat": "Source push timestamps, optimistic displayed-touch fills, no funding or impact."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = score(args.source_directory)
    result = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    print(result, end="")


if __name__ == "__main__":
    main()
