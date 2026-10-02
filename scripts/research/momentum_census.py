"""Run Experiment MOM-000 (census, no model) over acquired archives.

Usage: python3 scripts/research/momentum_census.py <data-dir> <report.json>
"""

from __future__ import annotations

import hashlib
import json
import sys

from rocket.momentum.acquire import load_all_texts
from rocket.momentum.bars import aggregate_4h, parse_kline_csv
from rocket.momentum.census import run_census


def main() -> int:
    directory, report_path = sys.argv[1], sys.argv[2]
    texts = load_all_texts(directory)
    rows_1h = []
    quarantine: list = []
    for i, text in enumerate(texts["spot_1h"]):
        rows_1h.extend(parse_kline_csv(
            text, vintage=f"binance-spot-1h-file{i:03d}", ingested_at="acquire-manifest",
            quarantine=quarantine))
    fingerprint = hashlib.sha256(
        "".join(sorted(t[:64] + t[-64:] for t in texts["spot_1h"])).encode()
    ).hexdigest()[:32]
    rows_1h.sort(key=lambda r: r["open_ms"])
    bars_4h = aggregate_4h(rows_1h)
    report = run_census(bars_4h, rows_1h, source_fingerprint=fingerprint,
                        quarantined_rows=quarantine)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(
        {"n_crossings": report["n_crossings"], "n_spaced": report["n_spaced"],
         "UP_independent": report["UP"]["independent"],
         "DOWN_independent": report["DOWN"]["independent"],
         "quarantined_rows": report["quarantined_rows"],
         "gate": report["gate"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
