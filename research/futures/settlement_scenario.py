"""Provisional FUT-001 discovery scenarios for documented cessation events.

This is a sensitivity calculation, not the accepted FUT-001 result. It never
reports 2025 OOS performance and refuses to summarize unresolved exposures.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from research.futures.fut001 import (
    DAY_MS,
    END_MS,
    START_MS,
    desired_weights,
    funding_window,
    generate_signals,
    partition,
    signal_statistic,
    summarize,
)

DISCOVERY_END_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
PRICE_STRESS = 0.05


def reconstruct(db: sqlite3.Connection, signals: dict, candidates: list[dict]) -> dict:
    """Attach candidate exits and funding only where a same-day entry exists."""
    events = {}
    for candidate in candidates:
        symbol = candidate["symbol"]
        day = int(datetime.fromisoformat(candidate["date"] + "T00:00:00+00:00").timestamp() * 1000)
        item = signals.get(day, {}).get(symbol)
        if item is None:
            raise ValueError(f"cessation event has no eligible entry: {symbol} {candidate['date']}")
        row = db.execute("SELECT open,tradable FROM prices WHERE symbol=? AND open_ms=?",
                         (symbol, day)).fetchone()
        if row is None or not row[1] or row[0] <= 0:
            raise ValueError(f"cessation event has no valid entry open: {symbol} {candidate['date']}")
        funding = list(db.execute("SELECT slot_ms,stamp_ms,interval_hours,rate FROM funding "
                                  "WHERE symbol=? ORDER BY slot_ms", (symbol,)))
        ok, amount = funding_window(funding, [record[0] for record in funding],
                                    day, candidate["assumed_settlement_ms"],
                                    allow_end_record=True)
        if not ok:
            raise ValueError(f"funding gap before settlement: {symbol} {candidate['date']}")
        later_funding = sum(record[3] for record in funding
                            if candidate["assumed_settlement_ms"] < record[1]
                            <= candidate["latest_candidate_settlement_ms"])
        if candidate["assumed_settlement_ms"] <= day or \
           candidate["assumed_settlement_ms"] >= day + DAY_MS:
            raise ValueError(f"invalid settlement cutoff: {symbol} {candidate['date']}")
        prices = (candidate["cutoff_sensitivity_mean_low"],
                  candidate["approx_index_settlement_price"],
                  candidate["cutoff_sensitivity_mean_high"])
        if any(price is None or price <= 0 for price in prices) or not prices[0] <= prices[1] <= prices[2]:
            raise ValueError(f"invalid settlement envelope: {symbol} {candidate['date']}")
        item["unresolved"] = []
        item["funding"] = amount
        item["return"] = prices[1] / row[0] - 1
        events[(day, symbol)] = {"open": row[0], "low": prices[0],
                                 "mid": prices[1], "high": prices[2],
                                 "funding_official": amount,
                                 "funding_low": min(amount, amount + later_funding),
                                 "funding_high": max(amount, amount + later_funding),
                                 "status": candidate["status"]}
    return events


def scenario_return(event: dict, weight: float, scenario: str) -> float:
    if scenario == "mid":
        price = event["mid"]
    elif scenario in ("adverse", "adverse_stress"):
        price = event["low"] if weight > 0 else event["high"]
        if scenario == "adverse_stress":
            price *= 1 - PRICE_STRESS if weight > 0 else 1 + PRICE_STRESS
    elif scenario in ("favorable", "favorable_stress"):
        price = event["high"] if weight > 0 else event["low"]
        if scenario == "favorable_stress":
            price *= 1 + PRICE_STRESS if weight > 0 else 1 - PRICE_STRESS
    else:
        raise ValueError(scenario)
    return price / event["open"] - 1


def scenario_funding(event: dict, weight: float, scenario: str) -> float:
    if scenario == "mid":
        return event["funding_official"]
    if scenario in ("adverse", "adverse_stress"):
        return event["funding_high"] if weight > 0 else event["funding_low"]
    if scenario in ("favorable", "favorable_stress"):
        return event["funding_low"] if weight > 0 else event["funding_high"]
    raise ValueError(scenario)


def monthly_bootstrap(days: list[dict], *, repetitions: int = 10_000) -> dict:
    """Resample whole calendar months so overlapping daily exposures stay together."""
    groups = defaultdict(list)
    for row in days:
        month = datetime.fromtimestamp(row["entry_ms"] / 1000, UTC).strftime("%Y-%m")
        groups[month].append(row["net"])
    blocks = [(sum(values), len(values)) for _, values in sorted(groups.items())]
    if not blocks:
        return {"months": 0, "mean_daily_net_ci95": None, "fraction_positive": None}
    rng = random.Random(20260924)
    means = []
    for _ in range(repetitions):
        sample = [rng.choice(blocks) for _ in blocks]
        means.append(sum(item[0] for item in sample) / sum(item[1] for item in sample))
    means.sort()
    return {"months": len(blocks), "repetitions": repetitions,
            "seed": 20260924,
            "mean_daily_net_ci95": [means[int(.025 * repetitions)],
                                    means[int(.975 * repetitions)]],
            "fraction_positive": sum(value > 0 for value in means) / repetitions}


def score_period(signals: dict, fills: dict, events: dict, *, period: str,
                 component: str, bps: int, scenario: str) -> dict:
    """Keep rejected next-day orders in cash and close settled positions intraday."""
    if bps not in (20, 40):
        raise ValueError("unfrozen cost scenario")
    if period not in ("discovery", "oos"):
        raise ValueError(period)
    start, end = ((START_MS, DISCOVERY_END_MS) if period == "discovery"
                  else (DISCOVERY_END_MS, END_MS))
    previous = {}
    days = []
    unresolved = []
    rejected_orders = 0
    forced_settlements = 0
    asset_gross = defaultdict(float)
    side_gross = defaultdict(float)
    for day in range(start, end, DAY_MS):
        if partition(day) != period:
            previous = {}
            continue
        current = signals.get(day, {})
        weights = desired_weights(current, component)
        for symbol, weight in list(weights.items()):
            if weight and not fills.get(day, {}).get(symbol, False):
                weights[symbol] = 0.0
                rejected_orders += 1
        for symbol, weight in previous.items():
            if weight and not fills.get(day, {}).get(symbol, False):
                unresolved.append({"day": day, "symbol": symbol, "reason": "unfilled_rebalance_or_exit"})
        turnover = sum(abs(weights.get(symbol, 0) - previous.get(symbol, 0))
                       for symbol in weights.keys() | previous.keys())
        gross = funding_drag = 0.0
        settled = set()
        for symbol, weight in weights.items():
            if weight == 0:
                continue
            item = current[symbol]
            if item["unresolved"]:
                unresolved.append({"day": day, "symbol": symbol, "reasons": item["unresolved"]})
                continue
            event = events.get((day, symbol))
            result = scenario_return(event, weight, scenario) if event else item["return"]
            contribution = weight * result
            gross += contribution
            asset_gross[symbol] += contribution
            side_gross["long" if weight > 0 else "short"] += contribution
            funding_drag += weight * (scenario_funding(event, weight, scenario)
                                      if event else item["funding"])
            if event:
                turnover += abs(weight)
                settled.add(symbol)
                forced_settlements += 1
        cost = turnover * bps / 20_000
        days.append({"partition": period, "entry_ms": day,
                     "gross": gross, "funding_drag": funding_drag,
                     "transaction_drag": cost, "net": gross - funding_drag - cost,
                     "gross_exposure": sum(abs(weight) for weight in weights.values()),
                     "active_names": sum(weight != 0 for weight in weights.values())})
        previous = {symbol: weight for symbol, weight in weights.items()
                    if weight and symbol not in settled}
    return {"period": period, "component": component,
            "round_trip_bps": bps, "scenario": scenario,
            "status": "INCOMPLETE_DATA" if unresolved else "PROVISIONAL_SETTLEMENT_SCENARIO",
            "unresolved_exposures": unresolved, "rejected_orders": rejected_orders,
            "forced_settlements": forced_settlements,
            "asset_gross": dict(sorted(asset_gross.items())),
            "side_gross": dict(side_gross),
            "bootstrap": monthly_bootstrap(days) if not unresolved else None,
            period: summarize(days, period) if not unresolved else None}


def score_discovery(signals: dict, fills: dict, events: dict, *, component: str,
                    bps: int, scenario: str) -> dict:
    return score_period(signals, fills, events, period="discovery",
                        component=component, bps=bps, scenario=scenario)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--period", choices=("discovery", "oos"), default="discovery")
    args = parser.parse_args()
    db = sqlite3.connect(args.database)
    signals, _, fills = generate_signals(db)
    candidates = json.loads(args.candidates.read_text())["events"]
    events = reconstruct(db, signals, candidates)
    results = [score_period(signals, fills, events, period=args.period,
                            component=component, bps=bps, scenario=scenario)
               for component in ("multi", "single")
               for bps in (20, 40)
               for scenario in ("adverse_stress", "adverse", "mid", "favorable",
                                "favorable_stress")]
    report = {"meaning": "provisional settlement sensitivity; not accepted FUT-001 PnL",
              "period": args.period, "price_stress_fraction": PRICE_STRESS,
              "candidate_events": len(events),
              "events_requiring_source_investigation": sum(
                  event["status"] == "REQUIRES_SOURCE_INVESTIGATION" for event in events.values()),
              "gross_signal_statistic": {
                  component: signal_statistic(signals, component).get(args.period)
                  for component in ("multi", "single")},
              "results": results}
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({"events": len(events),
                      "unresolved_by_scenario": [len(result["unresolved_exposures"]) for result in results],
                      "report": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
