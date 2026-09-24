"""Score the predeclared FUT-002 earlier-year replication without parameter search."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from research.futures.fut001 import generate_signals
from research.futures.settlement_scenario import PRICE_STRESS, reconstruct, score_window


def year_ms(year: int) -> int:
    return int(datetime(year, 1, 1, tzinfo=UTC).timestamp() * 1000)


def digest(path: Path) -> str:
    hash_value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hash_value.update(chunk)
    return hash_value.hexdigest()


def gross_statistic(signals: dict, component: str, start_ms: int, end_ms: int) -> dict:
    values = [item[component] * item["return"]
              for day, candidates in signals.items() if start_ms <= day < end_ms
              for item in candidates.values()
              if not item["unresolved"] and item["return"] is not None]
    return {"symbol_days": len(values),
            "mean_forecast_times_return": sum(values) / len(values) if values else None}


def run(database: Path, candidate_path: Path) -> dict:
    db = sqlite3.connect(database)
    try:
        signals, eligibility, fills = generate_signals(db,
                                                       start_ms=year_ms(2021),
                                                       end_ms=year_ms(2023))
        candidates = json.loads(candidate_path.read_text())["events"]
        events = reconstruct(db, signals, candidates)
        if len(events) != len(candidates) or len(events) != 13:
            raise ValueError("frozen cessation calendar does not match the reconstructed events")
        periods = (("2021", year_ms(2021), year_ms(2022)),
                   ("2022", year_ms(2022), year_ms(2023)),
                   ("combined", year_ms(2021), year_ms(2023)))
        results = [score_window(signals, fills, events,
                                start=start, end=end, label=label,
                                component=component, bps=bps, scenario=scenario)
                   for label, start, end in periods
                   for component in ("single", "multi")
                   for bps in (20, 40)
                   for scenario in ("adverse_stress", "adverse", "mid", "favorable",
                                    "favorable_stress")]
        if any(result["unresolved_exposures"] for result in results):
            raise ValueError("unresolved exposed outcome; replication interpretation prohibited")
        predictive = {component: {
            label: gross_statistic(signals, component, start, end)
            for label, start, end in periods}
            for component in ("single", "multi")}
        return {"meaning": "FUT-002 retrospective replication of selected 60-day control; "
                           "provisional settlement bounds, not a live-trading decision",
                "database_sha256": digest(database),
                "candidate_sha256": digest(candidate_path),
                "candidate_events": len(events),
                "events_requiring_source_investigation": sum(
                    event["status"] == "REQUIRES_SOURCE_INVESTIGATION"
                    for event in events.values()),
                "price_stress_fraction": PRICE_STRESS,
                "eligibility": eligibility,
                "gross_signal_statistic": predictive,
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
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({"results": len(report["results"]),
                      "candidate_events": report["candidate_events"],
                      "report": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
