"""Assemble only FUT-004 selected closure candidates before outcome scoring.

All event candidates predate this pack except ANC and COCOS, whose official
notice/minute-index sources are separately recorded. This validates source
coverage and prior-to-cutoff funding, not settlement returns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from research.futures.fut001 import funding_window
from research.futures.normalize_archives import DAY_MS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(database: Path, candidates: dict, sources: list[Path]) -> dict:
    catalog = {}
    for path in sources:
        for item in json.loads(path.read_text())["events"]:
            key = (item["date"], item["symbol"])
            if key in catalog:
                raise ValueError(f"duplicate settlement candidate: {key}")
            catalog[key] = item
    held = {(item["day"], item["symbol"]) for item in candidates["issues"]
            if item["reason"] == "held_missing_or_inactive_next_open"}
    if not held:
        raise ValueError("no selected closure cases")
    events = []
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        for day, symbol in sorted(held):
            item = catalog.get((day, symbol))
            if item is None:
                raise ValueError(f"missing selected settlement candidate: {day} {symbol}")
            entry = int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000)
            cutoff = item["assumed_settlement_ms"]
            if not entry < cutoff < entry + DAY_MS:
                raise ValueError(f"settlement outside held day: {day} {symbol}")
            low, mid, high = (item["cutoff_sensitivity_mean_low"],
                              item["approx_index_settlement_price"],
                              item["cutoff_sensitivity_mean_high"])
            if any(value is None or value <= 0 for value in (low, mid, high)) or not low <= mid <= high:
                raise ValueError(f"invalid index price envelope: {day} {symbol}")
            funding = list(db.execute(
                "SELECT slot_ms,stamp_ms,interval_hours,rate FROM funding "
                "WHERE symbol=? ORDER BY slot_ms", (symbol,)))
            ok, _ = funding_window(funding, [row[0] for row in funding],
                                   entry, cutoff, allow_end_record=True)
            if not ok:
                raise ValueError(f"incomplete held funding through cutoff: {day} {symbol}")
            events.append({**item, "funding_through_cutoff_verified": True})
    return {"generated_at": datetime.now(UTC).isoformat(),
            "meaning": "pre-result selected closure data pack; minute-index prices provisional",
            "candidate_manifest_sha256": hashlib.sha256(json.dumps(candidates, sort_keys=True).encode()).hexdigest(),
            "source_report_sha256": {str(path): sha256(path) for path in sources},
            "events": events}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("futures_database", type=Path)
    parser.add_argument("candidate_manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("source_candidates", nargs="+", type=Path)
    args = parser.parse_args()
    candidates = json.loads(args.candidate_manifest.read_text())
    report = build(args.futures_database, candidates, args.source_candidates)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({"selected_events": len(report["events"]),
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
