"""Return-free causal eligibility preflight on the audited 2022 Bybit tape."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from research.futures.fut001 import DAY_MS, MIN_QUOTE_VOLUME, funding_window

START = int(datetime(2022, 1, 1, tzinfo=UTC).timestamp() * 1000)
END = int(datetime(2023, 1, 1, tzinfo=UTC).timestamp() * 1000)
HOUR_MS = 3_600_000


def checked_rows(root: Path, sources: list[dict], kind: str) -> list:
    rows = []
    for source in sources:
        if f"_{kind}_" not in source["key"]:
            continue
        raw = (root / source["key"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(f"Bybit source hash changed: {source['key']}")
        payload = json.loads(raw)
        records = payload["result"]["list"]
        if len(records) != source["rows"]:
            raise ValueError(f"Bybit source row count changed: {source['key']}")
        rows.extend(records)
    return rows


def parse_prices(rows: list) -> tuple[dict[int, tuple[float, bool]], list[int]]:
    result = {}
    anomalies = []
    for row in rows:
        if len(row) != 7:
            raise ValueError("unexpected Bybit daily kline width")
        stamp = int(row[0])
        open_, high, low, close, volume, turnover = map(float, row[1:])
        if stamp % DAY_MS or stamp in result or volume < 0 or turnover < 0 or not all(
            math.isfinite(value) for value in (open_, high, low, close, volume, turnover)
        ):
            raise ValueError(f"invalid Bybit daily bar {stamp}")
        valid_ohlc = 0 < low <= min(open_, close) <= max(open_, close) <= high
        if not valid_ohlc:
            anomalies.append(stamp)
        tradable = valid_ohlc and volume > 0 and turnover > 0 and high > low
        result[stamp] = turnover, tradable
    return result, anomalies


def parse_funding(rows: list[dict]) -> list[tuple]:
    by_stamp = {}
    for row in rows:
        stamp = int(row["fundingRateTimestamp"])
        rate = float(row["fundingRate"])
        if stamp % HOUR_MS or stamp in by_stamp or not math.isfinite(rate) or not -1 <= rate <= 1:
            raise ValueError(f"invalid Bybit funding record {stamp}")
        by_stamp[stamp] = rate
    stamps = sorted(by_stamp)
    records = []
    for index, stamp in enumerate(stamps):
        neighbor = stamps[index - 1] if index else (stamps[1] if len(stamps) > 1 else None)
        if neighbor is None:
            raise ValueError("single funding record has unknown interval")
        interval = abs(stamp - neighbor) // HOUR_MS
        if not 1 <= interval <= 8:
            raise ValueError(f"unexpected Bybit funding interval: {stamp} {interval}")
        records.append((stamp, stamp, interval, by_stamp[stamp]))
    return records


def preflight_symbol(symbol: str, bars: dict[int, tuple[float, bool]],
                     funding: list[tuple]) -> tuple[Counter, list[dict]]:
    counts = Counter()
    issues = []
    slots = [row[0] for row in funding]
    for entry in range(START, END - DAY_MS, DAY_MS):
        counts["candidate_symbol_days"] += 1
        history = [bars.get(entry - step * DAY_MS) for step in range(1, 122)]
        if any(row is None or not row[1] for row in history):
            counts["invalid_or_gap_history"] += 1
            continue
        if sum(row[0] for row in history[:30]) / 30 < MIN_QUOTE_VOLUME:
            counts["below_liquidity_floor"] += 1
            continue
        funding_ok, _ = funding_window(funding, slots, entry - 30 * DAY_MS,
                                       entry)
        if not funding_ok:
            counts["incomplete_prior_funding"] += 1
            continue
        counts["eligible_symbol_days"] += 1
        entry_bar = bars.get(entry)
        exit_bar = bars.get(entry + DAY_MS)
        held_funding_ok, _ = funding_window(funding, slots, entry, entry + DAY_MS,
                                            allow_end_record=True)
        reasons = []
        if entry_bar is None or not entry_bar[1]:
            reasons.append("missing_or_inactive_entry")
        if exit_bar is None or not exit_bar[1]:
            reasons.append("missing_or_inactive_exit")
        if not held_funding_ok:
            reasons.append("incomplete_held_funding")
        if reasons:
            issues.append({"symbol": symbol, "entry_ms": entry, "reasons": reasons})
    return counts, issues


def run(coverage_path: Path, raw_root: Path) -> dict:
    manifest = json.loads(coverage_path.read_text())
    if manifest["failures"] or len(manifest["results"]) != manifest["candidate_count"]:
        raise ValueError("incomplete Bybit coverage inventory")
    totals = Counter()
    all_issues = []
    price_anomalies = []
    eligible_names = 0
    for item in manifest["results"]:
        bars, anomalies = parse_prices(checked_rows(raw_root, item["sources"], "daily"))
        price_anomalies.extend({"symbol": item["symbol"], "open_ms": stamp}
                               for stamp in anomalies)
        funding = parse_funding(checked_rows(raw_root, item["sources"], "funding"))
        counts, issues = preflight_symbol(item["symbol"], bars, funding)
        totals.update(counts)
        eligible_names += counts["eligible_symbol_days"] > 0
        all_issues.extend(issues)
    return {"meaning": "2022 Bybit causal eligibility and exposed data issues; no returns scored",
            "coverage_sha256": hashlib.sha256(coverage_path.read_bytes()).hexdigest(),
            "candidate_names": manifest["candidate_count"],
            "symbols_with_eligibility": eligible_names,
            "invalid_ohlc_bars": price_anomalies,
            "counts": dict(totals),
            "issues": sorted(all_issues, key=lambda item: (item["entry_ms"], item["symbol"]))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("raw_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = run(args.coverage, args.raw_root)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"counts": report["counts"],
                      "symbols_with_eligibility": report["symbols_with_eligibility"],
                      "issues": len(report["issues"]),
                      "report": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
