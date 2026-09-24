"""Build pre-result FUT-003 settlement scenarios from checked minute probes."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

LUNA_PRICE = 0.024  # Bybit API announcement: 2022-05-12 10:03 UTC


def build(probe: dict) -> list[dict]:
    candidates = []
    for item in probe["events"]:
        symbol = item["symbol"]
        cutoff = item["reported_delivery_ms"]
        if item["index_30m"] is None or item["index_60m"] is None:
            raise ValueError(f"missing Bybit index window: {symbol}")
        if item["last_active_trade_minute_ms"] != cutoff - 60_000:
            raise ValueError(f"unexpected Bybit last trade: {symbol}")
        if symbol == "LUNAUSDT":
            low = mid = high = LUNA_PRICE
            if float(item["index_at_cutoff"][4]) != LUNA_PRICE:
                raise ValueError("LUNA announcement and index close disagree")
            status = "ANNOUNCED_SPECIAL_SETTLEMENT"
        else:
            envelopes = (item["index_30m"], item["index_60m"])
            low = min(value["mean_low"] for value in envelopes)
            mid = item["index_30m"]["mean_close"]
            high = max(value["mean_high"] for value in envelopes)
            status = "PROVISIONAL_30_60_MINUTE_ENVELOPE"
        if not 0 < low <= mid <= high:
            raise ValueError(f"invalid Bybit settlement envelope: {symbol}")
        candidates.append({
            "symbol": symbol,
            "date": datetime.fromtimestamp(cutoff / 1000, UTC).date().isoformat(),
            "assumed_settlement_ms": cutoff,
            "latest_candidate_settlement_ms": cutoff,
            "approx_index_settlement_price": mid,
            "cutoff_sensitivity_mean_low": low,
            "cutoff_sensitivity_mean_high": high,
            "minute_trade_sha256": item["sources"]["trade"]["sha256"],
            "minute_index_sha256": item["sources"]["index"]["sha256"],
            "status": status,
        })
    if {item["symbol"] for item in candidates} != {"LUNAUSDT", "FTTUSDT", "SRMUSDT"}:
        raise ValueError("unexpected Bybit settlement set")
    return sorted(candidates, key=lambda item: item["symbol"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.probe.read_bytes()
    report = {"meaning": "unscored Bybit FUT-003 forced settlement candidates",
              "probe_sha256": hashlib.sha256(raw).hexdigest(),
              "events": build(json.loads(raw))}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"events": len(report["events"]), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
