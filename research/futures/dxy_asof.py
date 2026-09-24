"""Normalize an audited Yahoo/ICE DXY proxy without reading BTC outcomes.

Yahoo's daily timestamps label sessions, not publication times. Each valid
close becomes eligible only at 03:00 UTC on the following calendar date,
several hours after ICE's documented weekday publication window. Missing
sessions remain missing. This is a sparse proxy, not a paper replication.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo


SOURCE_SHA256 = "330480474ef50919a17998ffa2210471fde23d17dd2165319985299393754d88"
NEW_YORK = ZoneInfo("America/New_York")


def build_manifest(source: Path) -> dict:
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"source SHA-256 mismatch: {digest}")
    document = json.loads(raw)
    if document["chart"]["error"] is not None:
        raise ValueError("Yahoo chart returned an error")
    result, = document["chart"]["result"]
    meta = result["meta"]
    required = {"symbol": "DX-Y.NYB", "instrumentType": "INDEX",
                "exchangeTimezoneName": "America/New_York", "dataGranularity": "1d"}
    if any(meta.get(key) != value for key, value in required.items()):
        raise ValueError("unexpected Yahoo chart metadata")
    timestamps = result["timestamp"]
    quotes = result["indicators"]["quote"][0]
    if any(len(quotes[key]) != len(timestamps) for key in ("open", "high", "low", "close")):
        raise ValueError("timestamp and quote lengths differ")

    rows = []
    null_by_weekday = Counter()
    label_clock = Counter()
    seen = set()
    prior_stamp = None
    for index, stamp in enumerate(timestamps):
        if prior_stamp is not None and stamp <= prior_stamp:
            raise ValueError("duplicate or disordered source timestamp")
        prior_stamp = stamp
        label = dt.datetime.fromtimestamp(stamp, dt.timezone.utc).astimezone(NEW_YORK)
        date = label.date()
        if date in seen or not dt.date(2017, 1, 1) <= date <= dt.date(2025, 12, 31):
            raise ValueError("duplicate or out-of-range session date")
        seen.add(date)
        label_clock[label.strftime("%H:%M")] += 1
        close = quotes["close"][index]
        if close is None:
            null_by_weekday[str(date.weekday())] += 1
            continue
        if date.weekday() >= 5 or not math.isfinite(close) or close <= 0:
            raise ValueError("invalid non-null close")
        high, low = quotes["high"][index], quotes["low"][index]
        if high is None or low is None or not low <= close <= high:
            raise ValueError("close outside source high/low")
        # This timestamp is an explicit conservative policy, not Yahoo's bar timestamp.
        available = dt.datetime.combine(date + dt.timedelta(days=1),
                                        dt.time(3), dt.timezone.utc)
        if available.astimezone(NEW_YORK).date() != date:
            raise ValueError("availability clock does not fall after New York session")
        rows.append({"session_date_ny": date.isoformat(), "close": close,
                     "available_at_utc": available.isoformat()})

    return {"source": "Yahoo DX-Y.NYB daily INDEX proxy", "source_sha256": digest,
            "availability_policy": "03:00 UTC on calendar date after New York session",
            "null_by_weekday_monday_zero": dict(sorted(null_by_weekday.items())),
            "source_label_clock_ny": dict(sorted(label_clock.items())),
            "valid_by_year": dict(sorted(Counter(row["session_date_ny"][:4] for row in rows).items())),
            "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_manifest(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: value for key, value in manifest.items() if key != "rows"},
                     indent=2, sort_keys=True))
    print(f"valid_rows={len(manifest['rows'])}")


if __name__ == "__main__":
    main()
