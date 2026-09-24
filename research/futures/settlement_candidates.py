"""Build unscored settlement-price candidates from checked minute archives.

The default candidate cutoff is 09:00 UTC, with dated notice overrides. Each
notice must confirm the time and affected symbol before any row can repair
FUT-001 outcome data. Late trade minutes expand the price sensitivity through
the end of the last active minute. Minute index closes approximate, but do not
equal, the official second-level average.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from research.futures.settlement_probe import MINUTE_MS


def index_envelope(zip_path: Path, cutoff_ms: int, minutes: int) -> dict | None:
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if len(names) != 1:
            raise ValueError(f"unexpected index ZIP members: {zip_path}")
        rows = list(csv.reader(io.TextIOWrapper(archive.open(names[0]), encoding="utf-8-sig")))
    if rows and rows[0][0] == "open_time":
        rows = rows[1:]
    values = {int(row[0]): (float(row[3]), float(row[4]), float(row[2])) for row in rows}
    window = [values.get(cutoff_ms - step * MINUTE_MS)
              for step in range(1, minutes + 1)]
    if any(value is None for value in window):
        return None
    return {"mean_low": sum(value[0] for value in window) / minutes,
            "mean_close": sum(value[1] for value in window) / minutes,
            "mean_high": sum(value[2] for value in window) / minutes}


def index_mean(zip_path: Path, cutoff_ms: int, minutes: int) -> float | None:
    """Backward-compatible minute-close approximation for individual checks."""
    envelope = index_envelope(zip_path, cutoff_ms, minutes)
    return envelope["mean_close"] if envelope else None


def build(probes: dict, notices: dict, root: Path) -> list[dict]:
    by_date = {item["date"]: item for item in notices["events"]}
    candidates = {}
    for item in probes["results"]:
        last = item.get("last_active_minute_ms")
        if last is None:
            continue
        date = datetime.fromtimestamp(last / 1000, UTC).date().isoformat()
        notice = by_date.get(date)
        if notice is None:
            continue
        cutoff_time = notice.get("settlement_time_utc", "09:00")
        cutoff = int(datetime.fromisoformat(date + "T" + cutoff_time + ":00+00:00").timestamp() * 1000)
        minutes = 60 if date < "2024-11-11" else 30
        envelope = index_envelope(root / item["indexPriceKlines_key"], cutoff, minutes)
        latest_cutoff = max(cutoff, last + MINUTE_MS)
        alternatives = [index_envelope(root / item["indexPriceKlines_key"], candidate_cutoff,
                                       minutes)
                        for candidate_cutoff in range(cutoff, latest_cutoff + 1, MINUTE_MS)]
        conservative = None if any(value is None for value in alternatives) else {
            "low": min(value["mean_low"] for value in alternatives),
            "high": max(value["mean_high"] for value in alternatives),
        }
        candidate = {
            "symbol": item["symbol"], "date": date,
            "assumed_settlement_ms": cutoff,
            "last_active_minute_ms": last,
            "last_active_delta_minutes": (last - cutoff) / MINUTE_MS,
            "index_window_minutes": minutes,
            "approx_index_settlement_price": envelope["mean_close"] if envelope else None,
            "minute_index_mean_low": envelope["mean_low"] if envelope else None,
            "minute_index_mean_high": envelope["mean_high"] if envelope else None,
            "latest_candidate_settlement_ms": latest_cutoff,
            "cutoff_sensitivity_mean_low": conservative["low"] if conservative else None,
            "cutoff_sensitivity_mean_high": conservative["high"] if conservative else None,
            "minute_index_source_key": item["indexPriceKlines_key"],
            "minute_index_sha256": item["indexPriceKlines_sha256"],
            "minute_trade_source_key": item["klines_key"],
            "minute_trade_sha256": item["klines_sha256"],
            "notice_candidate_url": notice.get("symbol_sources", {}).get(
                item["symbol"], notice["source_url"]),
            "status": "UNVERIFIED_SYMBOL_TIME_AND_MINUTE_APPROXIMATION",
        }
        if envelope is None or conservative is None or last > cutoff:
            candidate["status"] = "REQUIRES_SOURCE_INVESTIGATION"
        candidates[(item["symbol"], date)] = candidate
    return [candidates[key] for key in sorted(candidates)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probes", type=Path)
    parser.add_argument("notices", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    events = build(json.loads(args.probes.read_text()),
                   json.loads(args.notices.read_text()), args.probes.parent)
    args.output.write_text(json.dumps({
        "meaning": "unscored minute-index settlement approximations, not accepted FUT-001 outcomes",
        "events": events,
    }, indent=2))
    print(json.dumps({"candidates": len(events),
                      "missing_index": sum(e["approx_index_settlement_price"] is None for e in events),
                      "source_investigations": sum(e["status"] == "REQUIRES_SOURCE_INVESTIGATION"
                                                   for e in events)}, indent=2))


if __name__ == "__main__":
    main()
