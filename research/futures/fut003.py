"""Score the frozen FUT-003 Bybit venue-transfer diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from research.futures.bybit_eligibility import END, START
from research.futures.fut001 import generate_signals
from research.futures.settlement_scenario import PRICE_STRESS, reconstruct, score_window


def digest(path: Path) -> str:
    hash_value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hash_value.update(chunk)
    return hash_value.hexdigest()


def gross_statistic(signals: dict, component: str) -> dict:
    values = [item[component] * item["return"]
              for day, candidates in signals.items() if START <= day < END - 86_400_000
              for item in candidates.values()
              if not item["unresolved"] and item["return"] is not None]
    return {"symbol_days": len(values),
            "mean_forecast_times_return": sum(values) / len(values) if values else None}


def run(database: Path, candidate_path: Path) -> dict:
    db = sqlite3.connect(database)
    try:
        signals, eligibility, fills = generate_signals(db, start_ms=START, end_ms=END)
        candidates = json.loads(candidate_path.read_text())["events"]
        events = reconstruct(db, signals, candidates)
        if len(events) != 3:
            raise ValueError("FUT-003 closure set changed")
        results = [score_window(signals, fills, events, start=START, end=END,
                                label="bybit_2022", component=component,
                                bps=bps, scenario=scenario)
                   for component in ("multi", "single")
                   for bps in (20, 40)
                   for scenario in ("adverse_stress", "adverse", "mid", "favorable",
                                    "favorable_stress")]
        for item in results:
            summary = item["bybit_2022"]
            item["total_turnover_notional"] = (summary["total_transaction_drag"]
                                               / (item["round_trip_bps"] / 20_000))
            item["mean_daily_turnover_notional"] = (item["total_turnover_notional"]
                                                    / summary["days"])
        if any(item["unresolved_exposures"] for item in results):
            raise ValueError("unresolved Bybit held outcome; FUT-003 score incomplete")
        return {"meaning": "FUT-003 Bybit 2022 transfer of old trend baseline; "
                           "provisional FTT/SRM settlement and costs, no promotion",
                "database_sha256": digest(database),
                "candidate_sha256": digest(candidate_path),
                "price_stress_fraction": PRICE_STRESS,
                "forced_settlement_events": len(events),
                "eligibility_including_unscored_december_31": eligibility,
                "gross_signal_statistic": {component: gross_statistic(signals, component)
                                           for component in ("multi", "single")},
                "results": results}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = run(args.database, args.candidates)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"results": len(report["results"]),
                      "events": report["forced_settlement_events"],
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
