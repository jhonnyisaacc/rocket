"""Score the frozen FUT-009 delayed dollar-index BTC pilot year by year."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import random
import sqlite3
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


DXY_SHA = "8c8427fa1ed62c38466fed10b4785d1754f8f25227100c8a7e053047a1143e40"
HOURLY_REPORT_SHA = "bcbcfdb4d6b5af752abf65edbbcff5258c9cdfacace0b948d5dcc7add7425af1"
FUNDING_DB_SHA = "e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b"
HOUR_MS = 3_600_000
DAY_MS = 24 * HOUR_MS


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check(path: Path, expected: str) -> None:
    if digest(path) != expected:
        raise ValueError(f"source fingerprint mismatch: {path}")


def ms(day: dt.date, hour: int) -> int:
    return int(dt.datetime.combine(day, dt.time(hour), dt.timezone.utc).timestamp() * 1000)


def source_rows(path: Path) -> list[dict]:
    check(path, DXY_SHA)
    report = json.loads(path.read_text())
    if report["source_sha256"] != "330480474ef50919a17998ffa2210471fde23d17dd2165319985299393754d88":
        raise ValueError("unexpected DXY raw source")
    rows = report["rows"]
    prior = None
    for row in rows:
        day = dt.date.fromisoformat(row["session_date_ny"])
        expected = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(3), dt.timezone.utc)
        if row["available_at_utc"] != expected.isoformat() or (prior and day <= prior):
            raise ValueError("noncausal or disordered DXY as-of row")
        prior = day
    return rows


def hourly_opens(folder: Path, report_path: Path, last_year: int) -> dict[int, float]:
    check(report_path, HOURLY_REPORT_SHA)
    report = json.loads(report_path.read_text())
    files = report["files"]
    if len(files) != 48:
        raise ValueError("unexpected BTC source report")
    opens = {}
    for item in files:
        name = item["source_key"]
        year = int(name.split("-")[2])
        if year > last_year:
            continue  # Do not read conditional 2025 price outcomes in the 2024 score.
        path = folder / name
        check(path, item["sha256"])
        with zipfile.ZipFile(path) as archive:
            member = name[:-4] + ".csv"
            if archive.namelist() != [member]:
                raise ValueError(f"unexpected hourly archive layout: {name}")
            with archive.open(member) as handle:
                reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8-sig"))
                next(reader)
                count = 0
                for row in reader:
                    stamp, price = int(row[0]), float(row[1])
                    if stamp in opens or price <= 0 or not math.isfinite(price):
                        raise ValueError(f"invalid duplicate hourly open: {name}")
                    opens[stamp] = price
                    count += 1
                if count != item["rows"]:
                    raise ValueError(f"hourly archive count changed: {name}")
    return opens


def source_features(rows: list[dict], last_day: dt.date) -> list[dict]:
    features = []
    previous = None
    for row in rows:
        day = dt.date.fromisoformat(row["session_date_ny"])
        if day > last_day:
            break
        if previous is not None and day >= dt.date(2022, 1, 3):
            prior_day = dt.date.fromisoformat(previous["session_date_ny"])
            if (day - prior_day).days <= 4:
                feature = math.log(row["close"] / previous["close"])
                decision, entry = ms(day + dt.timedelta(days=1), 3), ms(day + dt.timedelta(days=1), 4)
                features.append({"day": day, "x": feature, "decision": decision,
                                 "entry": entry, "exit": entry + DAY_MS})
        previous = row
    return features


def fit(pairs: list[dict]) -> tuple[float, float] | None:
    if len(pairs) < 200:
        return None
    mx = sum(pair["x"] for pair in pairs) / len(pairs)
    my = sum(pair["y"] for pair in pairs) / len(pairs)
    variance = sum((pair["x"] - mx) ** 2 for pair in pairs)
    if variance <= 0:
        return None
    slope = sum((pair["x"] - mx) * (pair["y"] - my) for pair in pairs) / variance
    intercept = my - slope * mx
    if not all(math.isfinite(value) for value in (intercept, slope)):
        return None
    return intercept, slope


def funding_rows(database: Path, year: int) -> dict[int, tuple[int, float]]:
    check(database, FUNDING_DB_SHA)
    start, end = ms(dt.date(year, 1, 1), 0), ms(dt.date(year + 1, 1, 1), 0)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT slot_ms,stamp_ms,rate FROM funding "
            "WHERE symbol='BTCUSDT' AND slot_ms>=? AND slot_ms<? ORDER BY slot_ms",
            (start, end)).fetchall()
    return {slot: (stamp, rate) for slot, stamp, rate in rows}


def funding_for_interval(funding: dict[int, tuple[int, float]], entry: int, exit_: int) -> float:
    expected = (entry + 4 * HOUR_MS, entry + 12 * HOUR_MS, entry + 20 * HOUR_MS)
    values = []
    for slot in expected:
        item = funding.get(slot)
        if item is None or not entry < item[0] <= exit_:
            raise ValueError(f"unresolved active funding: {slot}")
        values.append(item[1])
    return sum(values)


def score(year: int, dxy_path: Path, hourly_folder: Path, funding_db: Path,
          prior_result: Path | None = None) -> dict:
    if year not in (2024, 2025):
        raise ValueError("only the frozen 2024/2025 chronology is allowed")
    if year == 2025:
        if prior_result is None:
            raise ValueError("2025 requires a passing 2024 result")
        prior = json.loads(prior_result.read_text())
        if prior.get("experiment") != "FUT-009" or prior.get("year") != 2024 or not prior.get("passed_all_frozen_gates"):
            raise ValueError("2024 gate did not unlock 2025")
    if year == 2024:
        first_day, last_day = dt.date(2024, 3, 1), dt.date(2024, 12, 29)
    else:
        first_day, last_day = dt.date(2025, 1, 1), dt.date(2025, 12, 29)
    source = source_rows(dxy_path)
    opens = hourly_opens(hourly_folder, hourly_folder / "source_audit.json", year)
    funding = funding_rows(funding_db, year)
    features = source_features(source, last_day)
    candidates = []
    for feature in features:
        entry, exit_ = feature["entry"], feature["exit"]
        if entry in opens and exit_ in opens:
            candidates.append({**feature, "y": math.log(opens[exit_] / opens[entry])})
        elif feature["day"] >= first_day:
            raise ValueError(f"unresolved active price: {feature['day']}")
    if any(candidates[index]["exit"] > candidates[index + 1]["exit"]
           for index in range(len(candidates) - 1)):
        raise ValueError("training candidates disordered")

    by_day = {feature["day"]: feature for feature in features}
    first_entry = first_day + dt.timedelta(days=1)
    last_entry = last_day + dt.timedelta(days=1)
    day = first_entry
    scheduled = []
    old_target = 0
    training_cursor = 0
    completed = []
    while day <= last_entry:
        source_day = day - dt.timedelta(days=1)
        decision, entry, exit_ = ms(day, 3), ms(day, 4), ms(day + dt.timedelta(days=1), 4)
        while training_cursor < len(candidates) and candidates[training_cursor]["exit"] < decision:
            completed.append(candidates[training_cursor])
            training_cursor += 1
        feature = by_day.get(source_day)
        target = baseline = 0
        forecast = None
        if feature is not None:
            if feature["decision"] != decision or feature["entry"] != entry:
                raise ValueError("DXY decision clock mismatch")
            model = fit(completed)
            if model is None:
                raise ValueError(f"unresolved model fit after warmup: {source_day}")
            forecast = model[0] + model[1] * feature["x"]
            target = (forecast > 0) - (forecast < 0)
            intercept_only = sum(pair["y"] for pair in completed) / len(completed)
            baseline = ((intercept_only > 0) - (intercept_only < 0)) if target else 0
        price = opens.get(entry)
        exit_price = opens.get(exit_)
        if price is None or exit_price is None:
            if target:
                raise ValueError(f"unresolved active entry or exit: {day}")
            underlying = 0.0
        else:
            underlying = exit_price / price - 1
        funding_rate = funding_for_interval(funding, entry, exit_) if target else 0.0
        gross = target * underlying
        funding_pnl = -target * funding_rate
        turnover = abs(target - old_target)
        scheduled.append({"source_day": source_day.isoformat(), "entry_day": day.isoformat(),
                          "target": target, "intercept_only_target": baseline,
                          "forecast": forecast, "training_pairs": len(completed),
                          "underlying_return": underlying, "funding_rate": funding_rate,
                          "price_gross": gross, "always_long_gross": underlying if target else 0.0,
                          "intercept_only_gross": baseline * underlying,
                          "funding_pnl": funding_pnl, "turnover": turnover})
        old_target = target
        day += dt.timedelta(days=1)
    scheduled[-1]["turnover"] += abs(old_target)  # Terminal flatten at final exit.

    active = [row for row in scheduled if row["target"]]
    months = defaultdict(list)
    for row in scheduled:
        months[row["entry_day"][:7]].append(row)
    mean = lambda values: sum(values) / len(values) if values else 0.0
    gross_active = mean([row["price_gross"] for row in active])
    incremental = mean([row["price_gross"] - row["always_long_gross"] for row in active])
    longest_run = run = 0
    for row in scheduled:
        run = run + 1 if row["target"] else 0
        longest_run = max(longest_run, run)
    output = {"experiment": "FUT-009", "freeze_commit": "38ff532", "year": year,
              "source_window": [first_day.isoformat(), last_day.isoformat()],
              "scheduled_days": len(scheduled), "active_positions": len(active),
              "source_cash_days": sum(row["forecast"] is None for row in scheduled),
              "long_positions": sum(row["target"] == 1 for row in scheduled),
              "short_positions": sum(row["target"] == -1 for row in scheduled),
              "longest_active_run": longest_run,
              "min_training_pairs": min((row["training_pairs"] for row in active), default=0),
              "max_training_pairs": max((row["training_pairs"] for row in active), default=0),
              "active_price_gross_mean_bps": gross_active * 10000,
              "always_long_same_active_mean_bps": mean([row["always_long_gross"] for row in active]) * 10000,
              "intercept_only_same_active_mean_bps": mean([row["intercept_only_gross"] for row in active]) * 10000,
              "incremental_vs_always_long_mean_bps": incremental * 10000,
              "scheduled_price_gross_mean_bps": mean([row["price_gross"] for row in scheduled]) * 10000,
              "scheduled_funding_mean_bps": mean([row["funding_pnl"] for row in scheduled]) * 10000,
              "turnover_units": sum(row["turnover"] for row in scheduled),
              "long_price_gross_mean_bps": mean([row["price_gross"] for row in active
                                                  if row["target"] == 1]) * 10000,
              "short_price_gross_mean_bps": mean([row["price_gross"] for row in active
                                                   if row["target"] == -1]) * 10000,
              "monthly": {month: {"days": len(rows),
                                   "active": sum(bool(row["target"]) for row in rows),
                                   "gross_mean_bps": mean([row["price_gross"] for row in rows]) * 10000}
                          for month, rows in sorted(months.items())}}
    for side in (5, 10):
        nets = [row["price_gross"] + row["funding_pnl"] - row["turnover"] * side / 10000
                for row in scheduled]
        output[f"scheduled_net_{side}bp_side_mean_bps"] = mean(nets) * 10000
        product = 1.0
        peak = 1.0
        max_drawdown = 0.0
        for value in nets:
            product *= 1 + value
            peak = max(peak, product)
            max_drawdown = min(max_drawdown, product / peak - 1)
        output[f"scheduled_net_{side}bp_side_compounded_pct"] = (product - 1) * 100
        output[f"scheduled_net_{side}bp_side_max_drawdown_pct"] = max_drawdown * 100
        control_nets = {}
        for control in ("always_long", "intercept_only"):
            old = 0
            values = []
            for row in scheduled:
                target = (int(bool(row["target"])) if control == "always_long"
                          else row["intercept_only_target"])
                values.append(target * (row["underlying_return"] - row["funding_rate"])
                              - abs(target - old) * side / 10000)
                old = target
            values[-1] -= abs(old) * side / 10000
            control_nets[control] = mean(values) * 10000
        output[f"controls_net_{side}bp_side_mean_bps"] = control_nets
        month_nets = []
        for month, rows in sorted(months.items()):
            month_values = [row["price_gross"] + row["funding_pnl"]
                            - row["turnover"] * side / 10000 for row in rows]
            output["monthly"][month][f"net_{side}bp_side_mean_bps"] = mean(month_values) * 10000
            month_nets.append(month_values)
        rng = random.Random(20260924 + side + year)
        resampled = []
        for _ in range(10000):
            picks = [month_nets[rng.randrange(len(month_nets))] for _ in month_nets]
            resampled.append(sum(map(sum, picks)) / sum(map(len, picks)) * 10000)
        resampled.sort()
        output[f"net_{side}bp_side_month_block_95pct_bps"] = [resampled[249], resampled[9749]]
    output["sample_gate"] = len(active) >= 150
    output["gross_gate"] = gross_active > 0 and incremental > 0
    output["cost_gate"] = all(output[f"scheduled_net_{side}bp_side_mean_bps"] > 0
                              for side in (5, 10))
    output["passed_all_frozen_gates"] = all(
        output[key] for key in ("sample_gate", "gross_gate", "cost_gate"))
    output["attribution"] = "PILOT_PASS_REPLICATION_REQUIRED" if output["passed_all_frozen_gates"] else "SAMPLE_GROSS_OR_COST_GATE_FAILED"
    output["caveat"] = "Sparse Yahoo index proxy, optimistic hourly-open fills, no spread or impact."
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int, choices=(2024, 2025))
    parser.add_argument("dxy_asof", type=Path)
    parser.add_argument("hourly_folder", type=Path)
    parser.add_argument("funding_database", type=Path)
    parser.add_argument("--prior-result", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = score(args.year, args.dxy_asof, args.hourly_folder,
                   args.funding_database, args.prior_result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
