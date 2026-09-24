"""Provisional FUT-001 discovery scenarios for documented cessation events.

This is a sensitivity calculation, not the accepted FUT-001 result. It never
reports 2025 OOS performance and refuses to summarize unresolved exposures.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from research.futures.fut001 import (
    DAY_MS,
    START_MS,
    desired_weights,
    funding_window,
    generate_signals,
    partition,
    summarize,
)

DISCOVERY_END_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)


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
        if candidate["assumed_settlement_ms"] <= day or \
           candidate["assumed_settlement_ms"] >= day + DAY_MS:
            raise ValueError(f"invalid settlement cutoff: {symbol} {candidate['date']}")
        prices = (candidate["minute_index_mean_low"],
                  candidate["approx_index_settlement_price"],
                  candidate["minute_index_mean_high"])
        if any(price is None or price <= 0 for price in prices) or not prices[0] <= prices[1] <= prices[2]:
            raise ValueError(f"invalid settlement envelope: {symbol} {candidate['date']}")
        item["unresolved"] = []
        item["funding"] = amount
        events[(day, symbol)] = {"open": row[0], "low": prices[0],
                                 "mid": prices[1], "high": prices[2],
                                 "status": candidate["status"]}
    return events


def scenario_return(event: dict, weight: float, scenario: str) -> float:
    if scenario == "mid":
        price = event["mid"]
    elif scenario == "adverse":
        price = event["low"] if weight > 0 else event["high"]
    elif scenario == "favorable":
        price = event["high"] if weight > 0 else event["low"]
    else:
        raise ValueError(scenario)
    return price / event["open"] - 1


def score_discovery(signals: dict, fills: dict, events: dict, *, component: str,
                    bps: int, scenario: str) -> dict:
    """Keep rejected next-day orders in cash and close settled positions intraday."""
    if bps not in (20, 40):
        raise ValueError("unfrozen cost scenario")
    previous = {}
    days = []
    unresolved = []
    rejected_orders = 0
    forced_settlements = 0
    for day in range(START_MS, DISCOVERY_END_MS, DAY_MS):
        if partition(day) != "discovery":
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
            gross += weight * result
            funding_drag += weight * item["funding"]
            if event:
                turnover += abs(weight)
                settled.add(symbol)
                forced_settlements += 1
        cost = turnover * bps / 20_000
        days.append({"partition": "discovery", "entry_ms": day,
                     "gross": gross, "funding_drag": funding_drag,
                     "transaction_drag": cost, "net": gross - funding_drag - cost,
                     "gross_exposure": sum(abs(weight) for weight in weights.values()),
                     "active_names": sum(weight != 0 for weight in weights.values())})
        previous = {symbol: weight for symbol, weight in weights.items()
                    if weight and symbol not in settled}
    return {"component": component, "round_trip_bps": bps, "scenario": scenario,
            "status": "INCOMPLETE_DATA" if unresolved else "PROVISIONAL_SETTLEMENT_SCENARIO",
            "unresolved_exposures": unresolved, "rejected_orders": rejected_orders,
            "forced_settlements": forced_settlements,
            "discovery": summarize(days, "discovery") if not unresolved else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    db = sqlite3.connect(args.database)
    signals, _, fills = generate_signals(db)
    candidates = json.loads(args.candidates.read_text())["events"]
    events = reconstruct(db, signals, candidates)
    results = [score_discovery(signals, fills, events, component=component,
                               bps=bps, scenario=scenario)
               for component in ("multi", "single")
               for bps in (20, 40)
               for scenario in ("adverse", "mid", "favorable")]
    report = {"meaning": "provisional discovery sensitivity only; not accepted FUT-001 PnL",
              "candidate_events": len(events),
              "events_requiring_source_investigation": sum(
                  event["status"] == "REQUIRES_SOURCE_INVESTIGATION" for event in events.values()),
              "results": results}
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({"events": len(events),
                      "unresolved_by_scenario": [len(result["unresolved_exposures"]) for result in results],
                      "report": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
