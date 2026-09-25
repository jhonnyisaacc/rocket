"""Score only the frozen FUT-006 November–December 2024 cheap gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from research.futures.fut001 import funding_window

SYMBOLS = ("BTCUSDT", "ETHUSDT")
START = date(2024, 11, 1)
END = date(2024, 12, 31)
FUNDING_DB_SHA = "e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b"


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def source_windows(path: Path) -> dict[str, dict[tuple[str, str], dict]]:
    data = json.loads(path.read_text())
    if data["freeze_commit"] != "cfb8916" or set(data["sources"]) != set(SYMBOLS):
        raise ValueError("wrong FUT-006 source scope")
    results = {}
    for symbol in SYMBOLS:
        records = data["sources"][symbol]
        if len(records) != 62:
            raise ValueError(f"incomplete source dates: {symbol}")
        day = START
        lookup = {}
        for record in records:
            if record["symbol"] != symbol or record["day"] != day.isoformat():
                raise ValueError(f"source day/order mismatch: {symbol} {day}")
            if set(record["windows"]) != {"00:15", "12:15"}:
                raise ValueError(f"source windows changed: {symbol} {day}")
            for clock, window in record["windows"].items():
                if window["proxy_price"] is None or window["proxy_ms"] is None:
                    raise ValueError(f"missing proxy: {symbol} {day} {clock}")
                if day <= END and window["signal_rows"] <= 0:
                    raise ValueError(f"missing signal: {symbol} {day} {clock}")
                lookup[(day.isoformat(), clock)] = window
            day += timedelta(days=1)
        results[symbol] = lookup
    return results


def load_funding(path: Path) -> dict[str, tuple[list[tuple], list[int]]]:
    if sha256(path) != FUNDING_DB_SHA:
        raise ValueError("funding database fingerprint changed")
    output = {}
    with sqlite3.connect(path) as db:
        for symbol in SYMBOLS:
            rows = list(db.execute(
                "SELECT slot_ms,stamp_ms,interval_hours,rate FROM funding "
                "WHERE symbol=? AND slot_ms>=1730419200000 AND slot_ms<=1735776000000 "
                "ORDER BY slot_ms", (symbol,)))
            if not rows:
                raise ValueError(f"missing funding: {symbol}")
            output[symbol] = (rows, [row[0] for row in rows])
    return output


def next_slot(day: date, clock: str) -> tuple[str, str]:
    if clock == "00:15":
        return day.isoformat(), "12:15"
    return (day + timedelta(days=1)).isoformat(), "00:15"


def score_symbol(symbol: str, windows: dict, funding: tuple) -> list[dict]:
    entries = []
    prior = {"oi_sign": 0, "always_long": 0}
    day = START
    while day <= END:
        for clock in ("00:15", "12:15"):
            first = windows[(day.isoformat(), clock)]
            last = windows[next_slot(day, clock)]
            buy, sell = first["buy_qty"], first["sell_qty"]
            if buy + sell <= 0:
                raise ValueError(f"zero opening volume: {symbol} {day} {clock}")
            oi = (buy - sell) / (buy + sell)
            signal = 1 if oi > 0 else -1 if oi < 0 else 0
            start_ms, end_ms = first["proxy_ms"], last["proxy_ms"]
            if not 43_190_000 <= end_ms - start_ms <= 43_210_000:
                raise ValueError(f"unexpected holding interval: {symbol} {day} {clock}")
            ok, funding_sum = funding_window(*funding, start_ms, end_ms,
                                             allow_end_record=True)
            if not ok:
                raise ValueError(f"missing funding interval: {symbol} {day} {clock}")
            price_return = last["proxy_price"] / first["proxy_price"] - 1
            terminal = day == END and clock == "12:15"
            row = {"symbol": symbol, "day": day.isoformat(), "clock": clock,
                   "oi": oi, "signal_rows": first["signal_rows"],
                   "entry_ms": start_ms, "exit_ms": end_ms,
                   "entry_price": first["proxy_price"],
                   "exit_price": last["proxy_price"],
                   "price_return": price_return, "funding_rate": funding_sum}
            for name, target in (("oi_sign", signal), ("always_long", 1)):
                turnover = abs(target - prior[name]) + (abs(target) if terminal else 0)
                gross = target * price_return
                drag = target * funding_sum
                row[name] = {"target": target, "turnover": turnover,
                             "gross": gross, "funding_drag": drag,
                             "net_5bp_side": gross - drag - 0.0005 * turnover,
                             "net_10bp_side": gross - drag - 0.001 * turnover}
                prior[name] = target
            entries.append(row)
        day += timedelta(days=1)
    if len(entries) != 122:
        raise ValueError(f"wrong event count: {symbol}")
    return entries


def pool(symbol_rows: dict[str, list[dict]]) -> list[dict]:
    result = []
    for btc, eth in zip(symbol_rows["BTCUSDT"], symbol_rows["ETHUSDT"], strict=True):
        if (btc["day"], btc["clock"]) != (eth["day"], eth["clock"]):
            raise ValueError("unmatched portfolio intervals")
        row = {"day": btc["day"], "clock": btc["clock"]}
        for name in ("oi_sign", "always_long"):
            row[name] = {field: (btc[name][field] + eth[name][field]) / 2
                         for field in ("turnover", "gross", "funding_drag",
                                       "net_5bp_side", "net_10bp_side")}
        result.append(row)
    return result


def metrics(rows: list[dict], name: str) -> dict:
    output = {"intervals": len(rows),
              "turnover": sum(row[name]["turnover"] for row in rows)}
    for field in ("gross", "funding_drag", "net_5bp_side", "net_10bp_side"):
        values = [row[name][field] for row in rows]
        output["mean_" + field] = sum(values) / len(values)
        if field.startswith("net"):
            output["compounded_" + field] = math.prod(1 + x for x in values) - 1
    return output


def daily_bootstrap(rows: list[dict]) -> list[float]:
    blocks = defaultdict(list)
    for row in rows:
        blocks[row["day"]].append(row["oi_sign"]["net_5bp_side"])
    if len(blocks) != 61 or any(len(block) != 2 for block in blocks.values()):
        raise ValueError("daily bootstrap blocks incomplete")
    block_means = [sum(block) / 2 for block in blocks.values()]
    rng = random.Random(20260924)
    samples = sorted(sum(rng.choices(block_means, k=61)) / 61 for _ in range(10_000))
    return [samples[249], samples[9749]]


def summarize(symbol_rows: dict[str, list[dict]], pooled: list[dict]) -> dict:
    output = {"pooled": metrics(pooled, "oi_sign"),
              "always_long": metrics(pooled, "always_long"),
              "by_month": {}, "by_symbol": {},
              "pooled_daily_bootstrap_5bp_side_95pct": daily_bootstrap(pooled)}
    for month in ("2024-11", "2024-12"):
        selected = [row for row in pooled if row["day"].startswith(month)]
        output["by_month"][month] = metrics(selected, "oi_sign")
    for symbol in SYMBOLS:
        rows = symbol_rows[symbol]
        info = metrics(rows, "oi_sign")
        info["long_intervals"] = sum(row["oi_sign"]["target"] > 0 for row in rows)
        info["short_intervals"] = sum(row["oi_sign"]["target"] < 0 for row in rows)
        info["cash_intervals"] = sum(row["oi_sign"]["target"] == 0 for row in rows)
        output["by_symbol"][symbol] = info
    day_gross = defaultdict(float)
    for row in pooled:
        day_gross[row["day"]] += row["oi_sign"]["gross"]
    overall = sum(day_gross.values())
    output["best_five_days_gross_share_if_positive"] = (
        sum(sorted(day_gross.values(), reverse=True)[:5]) / overall
        if overall > 0 else None)
    focus = output["pooled"]
    output["cheap_gate_pass"] = all(focus["mean_" + field] > 0 for field in
                                    ("gross", "net_5bp_side", "net_10bp_side"))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_report", type=Path)
    parser.add_argument("funding_database", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    windows = source_windows(args.source_report)
    funding = load_funding(args.funding_database)
    symbol_rows = {symbol: score_symbol(symbol, windows[symbol], funding[symbol])
                   for symbol in SYMBOLS}
    pooled = pool(symbol_rows)
    report = {"scope": "FUT-006 frozen November-December 2024 cheap gate only",
              "freeze_commit": "cfb8916",
              "source_report_sha256": sha256(args.source_report),
              "funding_database_sha256": FUNDING_DB_SHA,
              "symbol_intervals": symbol_rows, "pooled_intervals": pooled,
              "summary": summarize(symbol_rows, pooled)}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
