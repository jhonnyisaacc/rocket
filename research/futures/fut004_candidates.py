"""Freeze FUT-004 daily basis ranks and preflight selected data without returns.

Run only on 2022–2023 discovery before its gross score. The output contains
weights and source-availability flags, never entry/exit prices or PnL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from research.futures.fut001 import funding_window
from research.futures.normalize_archives import DAY_MS

EXPECTED_FUTURES_SHA = "e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b"
EXPECTED_SPOT_SHA = "32e9f95a3a4a4773faaab4724d06aa66def137dc56457f063de0308c40f65de8"
EXPECTED_ELIGIBILITY_SHA = "1da30a992c2fd0778f7ac865f33a775884b1d227db350db7498f019c8d894888"


def require_hash(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"source fingerprint changed: {path}: {actual}")


def build(futures_db: Path, spot_db: Path, eligibility: dict) -> dict:
    choices = {day: names for day, names in eligibility["eligible_symbols_by_entry_day"].items()
               if day[:4] in ("2022", "2023")}
    selected = {}
    counts = Counter()
    issues = []
    with sqlite3.connect(f"file:{futures_db}?mode=ro", uri=True) as db:
        db.execute("ATTACH DATABASE ? AS spot", (f"file:{spot_db}?mode=ro",))
        future = {(symbol, stamp): (close, tradable) for symbol, stamp, close, tradable in db.execute(
            "SELECT symbol,open_ms,close,tradable FROM prices WHERE open_ms<?",
            (int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000),))}
        spot = {(symbol, stamp): (close, tradable) for symbol, stamp, close, tradable in db.execute(
            "SELECT symbol,open_ms,close,tradable FROM spot.prices WHERE open_ms<?",
            (int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000),))}
        fills = {(symbol, stamp): bool(tradable) for symbol, stamp, tradable in db.execute(
            "SELECT symbol,open_ms,tradable FROM prices WHERE open_ms<?",
            (int(datetime(2024, 1, 2, tzinfo=UTC).timestamp() * 1000),))}
        funding = {}
        for symbol, slot, stamp, interval, rate in db.execute(
                "SELECT symbol,slot_ms,stamp_ms,interval_hours,rate FROM funding ORDER BY symbol,slot_ms"):
            funding.setdefault(symbol, []).append((slot, stamp, interval, rate))
        slots = {symbol: [row[0] for row in rows] for symbol, rows in funding.items()}
        for day, names in sorted(choices.items()):
            stamp = int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000)
            if len(names) < 20:
                continue
            ranked = []
            for symbol in names:
                f = future.get((symbol, stamp - DAY_MS))
                s = spot.get((symbol, stamp - DAY_MS))
                if not f or not s or not f[1] or not s[1]:
                    raise ValueError(f"eligibility/source mismatch: {day} {symbol}")
                ranked.append((math.log(f[0] / s[0]), symbol))
            ranked.sort()
            k = len(ranked) // 4
            weights = {symbol: -0.5 / k for _, symbol in ranked[:k]}
            weights.update({symbol: 0.5 / k for _, symbol in ranked[-k:]})
            selected[day] = weights
            counts["ranked_days"] += 1
            counts["ranked_names"] += len(names)
            counts["selected_symbol_days"] += len(weights)
            for symbol, weight in weights.items():
                if not fills.get((symbol, stamp), False):
                    counts["rejected_entry_orders"] += 1
                    issues.append({"day": day, "symbol": symbol, "weight": weight,
                                   "reason": "missing_or_inactive_entry"})
                    continue
                if not fills.get((symbol, stamp + DAY_MS), False):
                    counts["held_missing_next_open"] += 1
                    issues.append({"day": day, "symbol": symbol, "weight": weight,
                                   "reason": "held_missing_or_inactive_next_open"})
                ok, _ = funding_window(funding.get(symbol, []), slots.get(symbol, []),
                                       stamp, stamp + DAY_MS, allow_end_record=True)
                if not ok:
                    counts["held_incomplete_funding"] += 1
                    issues.append({"day": day, "symbol": symbol, "weight": weight,
                                   "reason": "held_incomplete_funding"})
    return {"generated_at": datetime.now(UTC).isoformat(),
            "meaning": "frozen ranks and return-free selected-exposure preflight; no PnL",
            "period": "2022-2023 discovery only", "counts": dict(counts),
            "issues": issues, "weights_by_entry_day": selected}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("futures_database", type=Path)
    parser.add_argument("spot_database", type=Path)
    parser.add_argument("eligibility", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    for path, digest in ((args.futures_database, EXPECTED_FUTURES_SHA),
                         (args.spot_database, EXPECTED_SPOT_SHA),
                         (args.eligibility, EXPECTED_ELIGIBILITY_SHA)):
        require_hash(path, digest)
    report = build(args.futures_database, args.spot_database,
                   json.loads(args.eligibility.read_text()))
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({"counts": report["counts"], "issues": len(report["issues"]),
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
