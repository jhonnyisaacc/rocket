"""Probe historical Hyperliquid funding and daily candles without scoring returns.

Fixed two-day BTC/ETH windows check whether a paired-perpetual carry study has
the minimum venue history. Raw responses stay in ignored local research data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

DAY_MS = 86_400_000
HOUR_MS = 3_600_000
WINDOWS = (("BTC", "2024-01-01"), ("ETH", "2024-01-01"),
           ("BTC", "2025-01-01"), ("ETH", "2025-01-01"))
URL = "https://api.hyperliquid.xyz/info"


def request_json(body: dict) -> tuple[bytes, list[dict]]:
    request = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 3:
                raise
            time.sleep(25)
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError(f"unexpected Hyperliquid response for {body['type']}")
    return raw, payload


def probe(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for coin, day in WINDOWS:
        start = int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000)
        end = start + 2 * DAY_MS
        for kind in ("fundingHistory", "candleSnapshot"):
            body = ({"type": kind, "coin": coin, "startTime": start, "endTime": end}
                    if kind == "fundingHistory" else
                    {"type": kind, "req": {"coin": coin, "interval": "1d",
                                           "startTime": start, "endTime": end}})
            name = f"{coin}_{day}_{kind}.json"
            path = output / name
            if path.exists():
                raw = path.read_bytes()
                payload = json.loads(raw)
            else:
                raw, payload = request_json(body)
                path.write_bytes(raw)
            if not isinstance(payload, list):
                raise ValueError(f"invalid cached response: {name}")
            stamp_key = "time" if kind == "fundingHistory" else "t"
            # The candle endpoint can include a candle whose start equals endTime.
            selected = [row for row in payload if start <= int(row[stamp_key]) < end]
            stamps = [int(row[stamp_key]) for row in selected]
            if len(stamps) != len(set(stamps)) or len(stamps) != len(selected):
                raise ValueError(f"duplicate timestamps: {name}")
            if any(row.get("coin" if kind == "fundingHistory" else "s") != coin
                   for row in selected):
                raise ValueError(f"unexpected coin: {name}")
            interval = HOUR_MS if kind == "fundingHistory" else DAY_MS
            slots = [stamp // interval * interval for stamp in stamps]
            expected = list(range(start, end, interval))
            if slots != expected:
                raise ValueError(f"missing or misordered source interval: {name}")
            if kind == "fundingHistory" and any(
                    not -1 <= float(row["fundingRate"]) <= 1 for row in selected):
                raise ValueError(f"invalid funding rate: {name}")
            if kind == "candleSnapshot" and any(
                    row.get("i") != "1d" or int(row["T"]) != int(row["t"]) + DAY_MS - 1
                    or min(float(row["o"]), float(row["c"])) < float(row["l"])
                    or max(float(row["o"]), float(row["c"])) > float(row["h"])
                    for row in selected):
                raise ValueError(f"invalid daily candle: {name}")
            results.append({"coin": coin, "start_day": day, "kind": kind,
                            "raw_rows": len(payload), "in_window_rows": len(selected),
                            "first_ms": min(stamps), "last_ms": max(stamps),
                            "source_key": name, "sha256": hashlib.sha256(raw).hexdigest()})
    return {"retrieved_at": datetime.now(UTC).isoformat(),
            "meaning": "fixed historical source samples only; no carry or price return computed",
            "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(probe(args.output), indent=2))


if __name__ == "__main__":
    main()
