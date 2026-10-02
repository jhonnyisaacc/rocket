"""Score frozen FUT-007 ETH lower-tail funding on 2023H2 and 2024 only.

The scorer loads no 2025 funding-conditioned event; a January 2025 hourly
price and funding settlement are used solely to close the last 2024 entry.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import math
import random
import sqlite3
import zipfile
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from research.futures.fut001 import funding_window

SYMBOL = "ETHUSDT"
SOURCE_SHA = "263c64597d44619e45a23fe540182cc0ef2af9bf52b1216718634e79b363db1a"
FUNDING_SHA = "e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b"
DAY_MS = 86_400_000
HOUR_MS = 3_600_000
PARTITIONS = (("2023H2", date(2023, 7, 1), date(2024, 1, 1)),
              ("2024", date(2024, 1, 1), date(2025, 1, 1)))


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def ms(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)


def funding_rank(rate: float, prior: list[float]) -> float:
    if len(prior) < 300:
        raise ValueError("insufficient funding history")
    return (sum(value < rate for value in prior) +
            0.5 * sum(value == rate for value in prior)) / len(prior)


def load_prices(folder: Path) -> dict[int, tuple[float, float]]:
    manifest_path = folder / "source_audit.json"
    if sha256(manifest_path) != SOURCE_SHA:
        raise ValueError("hourly source manifest fingerprint changed")
    manifest = json.loads(manifest_path.read_text())
    files = manifest["files"]
    if len(files) != 36:
        raise ValueError("hourly source manifest incomplete")
    prices = {}
    for file in files:
        name = file["source_key"]
        # The January 2025 archive supplies the last 2024 exit only.
        if name > f"{SYMBOL}-1h-2025-01.zip":
            continue
        path = folder / name
        if sha256(path) != file["sha256"]:
            raise ValueError(f"hourly ZIP fingerprint changed: {name}")
        with zipfile.ZipFile(path) as archive:
            member = name.removesuffix(".zip") + ".csv"
            with archive.open(member) as handle:
                rows = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig"))
                for row in rows:
                    stamp = int(row["open_time"])
                    if stamp > ms(date(2025, 1, 1)) + HOUR_MS:
                        break
                    if stamp in prices:
                        raise ValueError(f"duplicate hourly price: {stamp}")
                    prices[stamp] = (float(row["open"]), float(row["close"]))
    return prices


def load_funding(database: Path) -> tuple[list[tuple], list[int]]:
    if sha256(database) != FUNDING_SHA:
        raise ValueError("funding database fingerprint changed")
    with sqlite3.connect(database) as db:
        rows = list(db.execute(
            "SELECT slot_ms,stamp_ms,interval_hours,rate FROM funding "
            "WHERE symbol=? AND slot_ms>=? AND slot_ms<=? ORDER BY slot_ms",
            (SYMBOL, ms(date(2023, 1, 1)), ms(date(2025, 1, 1)))))
    slots = [row[0] for row in rows]
    if any(row[2] != 8 for row in rows):
        raise ValueError("non-eight-hour funding record")
    return rows, slots


def score_partition(start: date, end: date, prices: dict,
                    funding: list[tuple], slots: list[int]) -> list[dict]:
    rows = []
    previous = {"lower_tail": 0, "always_long": 0}
    day = start
    while day < end:
        settlement = ms(day)
        idx = bisect.bisect_left(slots, settlement)
        if idx >= len(slots) or slots[idx] != settlement:
            raise ValueError(f"missing current funding: {day}")
        if not settlement <= funding[idx][1] < settlement + HOUR_MS:
            raise ValueError(f"late or early current funding stamp: {day}")
        first = bisect.bisect_left(slots, settlement - 180 * DAY_MS)
        prior = funding[first:idx]
        if len(prior) != 540 or any(
            record[0] != settlement - 180 * DAY_MS + j * 8 * HOUR_MS
            for j, record in enumerate(prior)):
            raise ValueError(f"incomplete 180-day funding reference: {day}")
        rate = funding[idx][3]
        percentile = funding_rank(rate, [record[3] for record in prior])
        target = int(percentile <= 0.10)
        entry_ms = settlement + HOUR_MS
        exit_ms = entry_ms + DAY_MS
        entry, exit_ = prices.get(entry_ms), prices.get(exit_ms)
        previous_close = prices.get(settlement - HOUR_MS)
        older_close = prices.get(settlement - 5 * HOUR_MS)
        if any(value is None for value in (entry, exit_, previous_close, older_close)):
            raise ValueError(f"missing hourly entry, exit or prior price: {day}")
        if not entry[0] > 0 or not exit_[0] > 0:
            raise ValueError(f"invalid fill proxy: {day}")
        ok, paid_rate = funding_window(funding, slots, entry_ms, exit_ms,
                                       allow_end_record=True)
        if not ok:
            raise ValueError(f"missing exposed funding: {day}")
        price_return = exit_[0] / entry[0] - 1
        row = {"day": day.isoformat(), "month": day.strftime("%Y-%m"),
               "current_rate": rate, "funding_percentile": percentile,
               "prior_4h_return": previous_close[1] / older_close[1] - 1,
               "price_return": price_return, "held_funding_rate": paid_rate}
        terminal = day == end - timedelta(days=1)
        for name, weight in (("lower_tail", target), ("always_long", 1)):
            turnover = abs(weight - previous[name]) + (abs(weight) if terminal else 0)
            gross = weight * price_return
            drag = weight * paid_rate
            row[name] = {"target": weight, "turnover": turnover,
                         "gross": gross, "funding_drag": drag,
                         "net_5bp_side": gross - drag - 0.0005 * turnover,
                         "net_10bp_side": gross - drag - 0.001 * turnover}
            previous[name] = weight
        rows.append(row)
        day += timedelta(days=1)
    return rows


def longest_run(rows: list[dict], value: int) -> int:
    longest = current = 0
    for row in rows:
        current = current + 1 if row["lower_tail"]["target"] == value else 0
        longest = max(longest, current)
    return longest


def drawdown(values: list[float]) -> float:
    wealth = peak = 1.0
    worst = 0.0
    for value in values:
        wealth *= 1 + value
        peak = max(peak, wealth)
        worst = min(worst, wealth / peak - 1)
    return worst


def metrics(rows: list[dict]) -> dict:
    events = [row for row in rows if row["lower_tail"]["target"]]
    output = {"days": len(rows), "events": len(events),
              "triggered_positive_actual_rate": sum(row["current_rate"] > 0 for row in events),
              "longest_signal_streak": longest_run(rows, 1),
              "longest_cash_gap": longest_run(rows, 0),
              "turnover": sum(row["lower_tail"]["turnover"] for row in rows),
              "mean_event_gross": (sum(row["lower_tail"]["gross"] for row in events) /
                                   len(events) if events else None),
              "mean_all_day_long_gross": sum(row["price_return"] for row in rows) / len(rows),
              "mean_event_prior_4h": (sum(row["prior_4h_return"] for row in events) /
                                      len(events) if events else None),
              "mean_nonevent_prior_4h": sum(row["prior_4h_return"] for row in rows
                                            if not row["lower_tail"]["target"]) /
                                            max(1, len(rows) - len(events))}
    output["event_minus_all_day_gross"] = (
        output["mean_event_gross"] - output["mean_all_day_long_gross"] if events else None)
    for name in ("lower_tail", "always_long"):
        output[name] = {}
        for field in ("gross", "funding_drag", "net_5bp_side", "net_10bp_side"):
            series = [row[name][field] for row in rows]
            output[name]["mean_" + field] = sum(series) / len(series)
            if field.startswith("net"):
                output[name]["compounded_" + field] = math.prod(1 + x for x in series) - 1
                output[name]["max_drawdown_" + field] = drawdown(series)
    monthly = defaultdict(list)
    for row in rows:
        monthly[row["month"]].append(row)
    output["months"] = {
        key: {"days": len(block),
              "events": sum(x["lower_tail"]["target"] for x in block),
              "net_5bp_side": sum(x["lower_tail"]["net_5bp_side"] for x in block)}
        for key, block in sorted(monthly.items())}
    return output


def bootstrap_months(rows: list[dict]) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["month"]].append(row)
    blocks = list(grouped.values())
    rng = random.Random(20260924)
    net_means = []
    incremental = []
    for _ in range(10_000):
        sample = [row for block in rng.choices(blocks, k=len(blocks)) for row in block]
        selected = [row for row in sample if row["lower_tail"]["target"]]
        if not selected:
            continue
        net_means.append(sum(row["lower_tail"]["net_5bp_side"] for row in sample) /
                         len(sample))
        incremental.append(sum(row["price_return"] for row in selected) / len(selected) -
                           sum(row["price_return"] for row in sample) / len(sample))
    if not net_means:
        return {"retained_draws": 0, "net_5bp_side_95pct": None,
                "event_minus_all_day_gross_95pct": None}
    net_means.sort()
    incremental.sort()
    lo = int(0.025 * len(net_means))
    hi = min(len(net_means) - 1, int(0.975 * len(net_means)))
    return {"retained_draws": len(net_means),
            "net_5bp_side_95pct": [net_means[lo], net_means[hi]],
            "event_minus_all_day_gross_95pct": [incremental[lo], incremental[hi]]}


def score(folder: Path, database: Path) -> dict:
    prices = load_prices(folder)
    funding, slots = load_funding(database)
    partitions = {name: score_partition(start, end, prices, funding, slots)
                  for name, start, end in PARTITIONS}
    summaries = {name: {**metrics(rows), "month_bootstrap": bootstrap_months(rows)}
                 for name, rows in partitions.items()}
    all_rows = [row for rows in partitions.values() for row in rows]
    combined_net10 = sum(row["lower_tail"]["net_10bp_side"] for row in all_rows) / len(all_rows)
    gate = (all(summary["events"] >= 15 and summary["mean_event_gross"] > 0 and
                summary["event_minus_all_day_gross"] > 0 and
                summary["lower_tail"]["mean_net_5bp_side"] > 0
                for summary in summaries.values()) and combined_net10 > 0)
    return {"scope": "FUT-007 frozen ETH 2023H2/2024 cheap gate only",
            "freeze_commit": "eac3c94", "source_report_sha256": SOURCE_SHA,
            "funding_database_sha256": FUNDING_SHA,
            "partitions": partitions, "summary": summaries,
            "combined_mean_net_10bp_side": combined_net10,
            "cheap_gate_pass": gate,
            "result_status": "SURVIVED_CHEAP_GATE" if gate else
                             "NO_SAMPLE" if any(s["events"] < 15 for s in summaries.values())
                             else "FROZEN_GATE_FAILED"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_folder", type=Path)
    parser.add_argument("funding_database", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = score(args.source_folder, args.funding_database)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"summary": report["summary"],
                      "combined_mean_net_10bp_side": report["combined_mean_net_10bp_side"],
                      "result_status": report["result_status"]}, indent=2))


if __name__ == "__main__":
    main()
