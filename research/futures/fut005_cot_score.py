"""Score frozen FUT-005 COT-change BTC trial on 2023–2024 only.

No 2025 COT-conditioned outcome or 2026 price is read by this command.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import sqlite3
import zipfile
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

from research.futures.cftc_cot_source_audit import CODE, YEARS, available_date
from research.futures.fut001 import DAY_MS, funding_window

SOURCE_SHA = "a51fc0dc3461ad67ddd85b9e531b60f783546dc91a28c9f5e635bb7a8d6a830a"
BINANCE_SHA = "e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b"
START = date(2023, 1, 1)
END = date(2025, 1, 1)
CONTROL_NAMES = ("cot_change", "always_long", "price_7d")


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load_cot(directory: Path) -> list[dict]:
    if sha256(directory / "source_audit.json") != SOURCE_SHA:
        raise ValueError("CFTC source audit fingerprint changed")
    manifest = json.loads((directory / "source_audit.json").read_text())
    expected = {item["source_key"]: item["sha256"] for item in manifest["files"]}
    rows = []
    for year in YEARS:
        path = directory / f"deacot{year}.zip"
        if sha256(path) != expected[path.name]:
            raise ValueError(f"CFTC archive fingerprint changed: {path.name}")
        with zipfile.ZipFile(path) as archive, archive.open("annual.txt") as handle:
            reader = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig"))
            for item in reader:
                if item["CFTC Contract Market Code"] != CODE:
                    continue
                asof = date.fromisoformat(item["As of Date in Form YYYY-MM-DD"])
                long = int(item["Noncommercial Positions-Long (All)"])
                short = int(item["Noncommercial Positions-Short (All)"])
                if long + short <= 0:
                    raise ValueError(f"zero noncommercial positioning: {asof}")
                rows.append({"asof": asof, "available": available_date(asof),
                             "balance": (short - long) / (short + long)})
    rows.sort(key=lambda row: row["asof"])
    if len(rows) != manifest["total_reports"]:
        raise ValueError("CFTC count changed")
    if [row["available"] for row in rows] != sorted(row["available"] for row in rows):
        raise ValueError("CFTC releases not chronological")
    for previous, current in zip(rows, rows[1:]):
        current["delta"] = current["balance"] - previous["balance"]
    rows[0]["delta"] = None
    return rows


def daily_targets(rows: list[dict], prices: dict[int, tuple], day: date) -> dict[str, int]:
    latest = next((row for row in reversed(rows) if row["available"] <= day), None)
    target = 0
    if latest is not None and latest["delta"] is not None and (day - latest["asof"]).days <= 21:
        target = 1 if latest["delta"] > 0 else -1 if latest["delta"] < 0 else 0
    open_ms = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)
    price_target = 0
    if target:
        prior = prices.get(open_ms - DAY_MS)
        older = prices.get(open_ms - 8 * DAY_MS)
        if prior is None or older is None:
            raise ValueError(f"missing prior BTC closes for price control: {day}")
        ratio = prior[1] / older[1]
        price_target = 1 if ratio > 1 else -1 if ratio < 1 else 0
    return {"cot_change": target, "always_long": int(target != 0),
            "price_7d": price_target}


def score_day(day: date, target: dict[str, int], previous: dict[str, int],
              prices: dict[int, tuple], funding: list[tuple], slots: list[int],
              *, terminal: bool) -> dict:
    start = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)
    end = start + DAY_MS
    entry, exit_ = prices.get(start), prices.get(end)
    if entry is None or exit_ is None or entry[0] <= 0 or exit_[0] <= 0:
        raise ValueError(f"missing exposed BTC price: {day}")
    ok, funding_rate = funding_window(funding, slots, start, end, allow_end_record=True)
    if not ok and any(target.values()):
        raise ValueError(f"missing exposed BTC funding: {day}")
    price_return = exit_[0] / entry[0] - 1
    result = {"day": day.isoformat(), "month": day.strftime("%Y-%m"),
              "price_return": price_return, "funding_rate": funding_rate}
    for name in CONTROL_NAMES:
        weight = target[name]
        turnover = abs(weight - previous[name]) + (abs(weight) if terminal else 0)
        gross = weight * price_return
        drag = weight * funding_rate
        result[name] = {"weight": weight, "gross": gross, "funding_drag": drag,
                        "turnover": turnover,
                        "net_20bps": gross - drag - 0.001 * turnover,
                        "net_40bps": gross - drag - 0.002 * turnover}
    return result


def score(cot_dir: Path, binance_db: Path) -> list[dict]:
    if sha256(binance_db) != BINANCE_SHA:
        raise ValueError("Binance research tape fingerprint changed")
    reports = load_cot(cot_dir)
    with sqlite3.connect(binance_db) as db:
        prices = {stamp: (open_, close) for stamp, open_, close in db.execute(
            "SELECT open_ms,open,close FROM prices WHERE symbol='BTCUSDT' "
            "AND open_ms>=? AND open_ms<=? ORDER BY open_ms",
            (int(datetime(2022, 12, 20, tzinfo=UTC).timestamp() * 1000),
             int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)))}
        funding = list(db.execute(
            "SELECT slot_ms,stamp_ms,interval_hours,rate FROM funding "
            "WHERE symbol='BTCUSDT' AND slot_ms>=? AND slot_ms<=? ORDER BY slot_ms",
            (int(datetime(2022, 12, 31, tzinfo=UTC).timestamp() * 1000),
             int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000))))
    slots = [record[0] for record in funding]
    daily = []
    previous = dict.fromkeys(CONTROL_NAMES, 0)
    for stamp in range(int(datetime(2023, 1, 1, tzinfo=UTC).timestamp() * 1000),
                       int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000), DAY_MS):
        day = datetime.fromtimestamp(stamp / 1000, UTC).date()
        if day.month == 1 and day.day == 1:
            previous = dict.fromkeys(CONTROL_NAMES, 0)
        target = daily_targets(reports, prices, day)
        terminal = day.month == 12 and day.day == 31
        daily.append(score_day(day, target, previous, prices, funding, slots,
                               terminal=terminal))
        previous = target
    return daily


def bootstrap_months(daily: list[dict], name: str, field: str) -> list[float]:
    months = defaultdict(list)
    for row in daily:
        months[row["month"]].append(row[name][field])
    keys = sorted(months)
    rng = random.Random(20260924)
    means = []
    for _ in range(10_000):
        sample = [months[keys[rng.randrange(len(keys))]] for _ in keys]
        means.append(sum(sum(block) for block in sample) / sum(map(len, sample)))
    means.sort()
    return [means[249], means[9749]]


def summarize(daily: list[dict]) -> dict:
    result = {}
    for year in (2023, 2024):
        rows = [row for row in daily if row["day"].startswith(str(year))]
        result[str(year)] = {}
        for name in CONTROL_NAMES:
            info = {"active_days": sum(row[name]["weight"] != 0 for row in rows),
                    "long_days": sum(row[name]["weight"] > 0 for row in rows),
                    "short_days": sum(row[name]["weight"] < 0 for row in rows),
                    "turnover": sum(row[name]["turnover"] for row in rows)}
            for field in ("gross", "funding_drag", "net_20bps", "net_40bps"):
                series = [row[name][field] for row in rows]
                info[f"mean_daily_{field}"] = sum(series) / len(series)
                if field.startswith("net"):
                    info[f"compounded_{field}"] = math.prod(1 + value for value in series) - 1
            result[str(year)][name] = info
    result["cot_combined_bootstrap_20bps"] = bootstrap_months(daily, "cot_change", "net_20bps")
    cot = [result[str(year)]["cot_change"] for year in (2023, 2024)]
    result["cheap_gate_pass"] = all(item["mean_daily_gross"] > 0 and
                                   item["mean_daily_net_20bps"] > 0 for item in cot)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cot_dir", type=Path)
    parser.add_argument("binance_db", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    daily = score(args.cot_dir, args.binance_db)
    report = {"scope": "FUT-005 frozen 2023-2024 cheap gate only",
              "source_sha256": SOURCE_SHA, "binance_sha256": BINANCE_SHA,
              "daily": daily, "summary": summarize(daily)}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
