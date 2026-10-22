"""Run Experiment MOM-001 (reserved packet) over acquired archives.

Usage: python3 scripts/research/momentum_experiment1.py <data-dir> <census.json> <report.json>
Refuses to score unless the census gate passed.
"""

from __future__ import annotations

import json
import sys

from rocket.momentum.acquire import load_all_texts
from rocket.momentum.bars import aggregate_4h, parse_kline_csv
from rocket.momentum.candidates import scan_crossings, space_candidates
from rocket.momentum.experiment1 import build_rows, run_experiment_1
from rocket.momentum.features import parse_funding_csv, parse_metrics_csv


def main() -> int:
    directory, census_path, report_path = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(census_path, encoding="utf-8") as handle:
        census = json.load(handle)
    texts = load_all_texts(directory)
    rows_1h = []
    for i, text in enumerate(texts["spot_1h"]):
        rows_1h.extend(parse_kline_csv(
            text, vintage=f"binance-spot-1h-file{i:03d}", ingested_at="acquire-manifest"))
    rows_1h.sort(key=lambda r: r["open_ms"])
    bars_4h = aggregate_4h(rows_1h)
    perp_1h = []
    for i, text in enumerate(texts["perp_1h"]):
        perp_1h.extend(parse_kline_csv(
            text, vintage=f"binance-perp-1h-file{i:03d}", ingested_at="acquire-manifest"))
    perp_1h.sort(key=lambda r: r["open_ms"])
    perp_4h = aggregate_4h(perp_1h)
    funding = []
    for text in texts["funding"]:
        funding.extend(parse_funding_csv(text))
    metrics_daily = []
    for text in texts["metrics"]:
        metrics_daily.extend(parse_metrics_csv(text))
    crossings = scan_crossings(bars_4h)
    spaced = [e for e in space_candidates(crossings) if e["independent"]]
    rows = build_rows(spaced, bars_4h, rows_1h, funding=funding,
                      metrics_daily=metrics_daily, perp_4h=perp_4h)
    report = run_experiment_1(rows, gate_report=census["gate"])
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps({"rows": len(rows), "folds": len(report["folds"]),
                      "verdict": report["verdict"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
