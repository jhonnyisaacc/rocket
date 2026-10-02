"""Score only FUT-004's frozen 2022–2023 gross-information gate.

Requires the exact pre-result weight and selected-settlement manifests. The
2024/2025 factor outcomes, funding/cost net, and 2026 holdout are not read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from research.futures.normalize_archives import DAY_MS

FUTURES_SHA = "e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b"
CANDIDATES_SHA = "9dc451efc91cca893f45b29791896fc608e9f55e5132692da8409b2927cfe4c2"
EVENTS_SHA = "1ff17aa4f3c3ea4f4fc1787764a2684d83ec4326fa8bb2747595c924ff6a75d7"
SCENARIOS = ("adverse_stress", "adverse", "mid", "favorable", "favorable_stress")
STRESS = 0.05


def require_hash(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"source fingerprint changed: {path}: {actual}")


def settlement_price(event: dict, weight: float, scenario: str) -> float:
    if scenario == "mid":
        price = event["approx_index_settlement_price"]
    elif scenario.startswith("adverse"):
        price = event["cutoff_sensitivity_mean_low"] if weight > 0 else \
            event["cutoff_sensitivity_mean_high"]
        if scenario.endswith("stress"):
            price *= 1 - STRESS if weight > 0 else 1 + STRESS
    elif scenario.startswith("favorable"):
        price = event["cutoff_sensitivity_mean_high"] if weight > 0 else \
            event["cutoff_sensitivity_mean_low"]
        if scenario.endswith("stress"):
            price *= 1 + STRESS if weight > 0 else 1 - STRESS
    else:
        raise ValueError(scenario)
    if price <= 0:
        raise ValueError("nonpositive settlement scenario")
    return price


def month_bootstrap(days: list[dict], repetitions: int = 10_000) -> dict:
    months = defaultdict(list)
    for item in days:
        months[item["day"][:7]].append(item["gross"])
    blocks = [(sum(values), len(values)) for _, values in sorted(months.items())]
    rng = random.Random(20260924)
    means = []
    for _ in range(repetitions):
        sample = [rng.choice(blocks) for _ in blocks]
        means.append(sum(total for total, _ in sample) / sum(count for _, count in sample))
    means.sort()
    return {"months": len(blocks), "repetitions": repetitions, "seed": 20260924,
            "mean_daily_gross_ci95": [means[int(.025 * repetitions)],
                                      means[int(.975 * repetitions)]],
            "fraction_positive": sum(value > 0 for value in means) / repetitions}


def summarize(days: list[dict]) -> dict:
    mean = sum(row["gross"] for row in days) / len(days)
    equity = peak = 1.0
    drawdown = 0.0
    for row in days:
        equity *= 1 + row["gross"]
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
    quarters = defaultdict(list)
    months = defaultdict(list)
    for row in days:
        date = datetime.fromisoformat(row["day"])
        quarters[f"{date.year}-Q{(date.month - 1) // 3 + 1}"].append(row["gross"])
        months[row["day"][:7]].append(row["gross"])
    variance = sum((row["gross"] - mean) ** 2 for row in days) / (len(days) - 1)
    return {"days": len(days), "mean_daily_gross": mean, "compounded_gross": equity - 1,
            "annualized_sharpe_gross": mean * math.sqrt(365 / variance) if variance else None,
            "max_drawdown_gross": drawdown,
            "mean_gross_exposure": sum(row["gross_exposure"] for row in days) / len(days),
            "quarter_means": {key: sum(v) / len(v) for key, v in sorted(quarters.items())},
            "month_means": {key: sum(v) / len(v) for key, v in sorted(months.items())}}


def score(database: Path, candidates: dict, event_pack: dict) -> dict:
    event_by_key = {(item["date"], item["symbol"]): item for item in event_pack["events"]}
    held = {(item["day"], item["symbol"]) for item in candidates["issues"]
            if item["reason"] == "held_missing_or_inactive_next_open"}
    if set(event_by_key) != held:
        raise ValueError("selected held events do not equal event pack")
    rejected = {(item["day"], item["symbol"]) for item in candidates["issues"]
                if item["reason"] == "missing_or_inactive_entry"}
    prices = {}
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        end = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000)
        for symbol, stamp, open_, tradable in db.execute(
                "SELECT symbol,open_ms,open,tradable FROM prices WHERE open_ms<?", (end,)):
            prices[(symbol, stamp)] = (open_, bool(tradable))
    by_scenario = {}
    for scenario in SCENARIOS:
        days = []
        asset_contributions = defaultdict(float)
        side_contributions = defaultdict(float)
        forced = 0
        for day, weights in sorted(candidates["weights_by_entry_day"].items()):
            stamp = int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000)
            gross = 0.0
            exposure = 0.0
            for symbol, weight in weights.items():
                if (day, symbol) in rejected:
                    continue
                entry = prices.get((symbol, stamp))
                if entry is None or not entry[1] or entry[0] <= 0:
                    raise ValueError(f"unresolved entry: {day} {symbol}")
                event = event_by_key.get((day, symbol))
                if event:
                    exit_price = settlement_price(event, weight, scenario)
                    forced += 1
                else:
                    exit_ = prices.get((symbol, stamp + DAY_MS))
                    if exit_ is None or not exit_[1] or exit_[0] <= 0:
                        raise ValueError(f"unresolved held exit: {day} {symbol}")
                    exit_price = exit_[0]
                contribution = weight * (exit_price / entry[0] - 1)
                gross += contribution
                exposure += abs(weight)
                asset_contributions[symbol] += contribution
                side_contributions["long" if weight > 0 else "short"] += contribution
            days.append({"day": day, "gross": gross, "gross_exposure": exposure})
        year_days = {year: [item for item in days if item["day"].startswith(year)]
                     for year in ("2022", "2023")}
        by_scenario[scenario] = {
            "by_year": {year: summarize(items) for year, items in year_days.items()},
            "combined": summarize(days), "combined_month_bootstrap": month_bootstrap(days),
            "forced_settlements": forced, "rejected_orders": len(rejected),
            "side_contributions": dict(side_contributions),
            "top_absolute_asset_contributions": sorted(asset_contributions.items(),
                                                       key=lambda item: abs(item[1]), reverse=True)[:20],
        }
    checks = {scenario: (item["by_year"]["2022"]["mean_daily_gross"] > 0
                         and item["by_year"]["2023"]["mean_daily_gross"] > 0
                         and item["combined_month_bootstrap"]["mean_daily_gross_ci95"][0] > 0)
              for scenario, item in by_scenario.items()}
    return {"scenarios": by_scenario, "gross_gate_by_scenario": checks,
            "verdict": "GROSS_GATE_PASS_BOUNDED" if all(checks.values()) else
            "GROSS_GATE_FAILED_BOUNDED" if not any(checks.values()) else
            "GROSS_GATE_SETTLEMENT_SENSITIVE"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("futures_database", type=Path)
    parser.add_argument("candidate_manifest", type=Path)
    parser.add_argument("event_pack", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    for path, expected in ((args.futures_database, FUTURES_SHA),
                           (args.candidate_manifest, CANDIDATES_SHA),
                           (args.event_pack, EVENTS_SHA)):
        require_hash(path, expected)
    result = score(args.futures_database, json.loads(args.candidate_manifest.read_text()),
                   json.loads(args.event_pack.read_text()))
    result["scored_at"] = datetime.now(UTC).isoformat()
    result["meaning"] = "FUT-004 frozen gross gate only; provisional settlement bounds"
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps({"verdict": result["verdict"],
                      "checks": result["gross_gate_by_scenario"],
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
