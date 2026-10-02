"""Prospective shadow collector: one append-only forecast record per run.

Intended schedule: UTC 00/04/08/12/16/20 with a 5-minute receipt
allowance (external scheduler invokes this script; the script itself is
stateless and read-only). Fetches recent BTCUSDT 1h spot klines,
aggregates the latest complete 4h bar, evaluates candgen-v1 candidate
state + feat-v1 Tier A snapshot, and appends a forecast record with NO
outcome fields. Missing/incomplete data appends UNKNOWN, never skips.

Usage: python3 scripts/research/momentum_shadow.py <shadow-dir>
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime, timedelta

from rocket.momentum.bars import aggregate_4h, contiguous_4h_before
from rocket.momentum.candidates import crossing_state, sigma_at
from rocket.momentum.features import tier_a
from rocket.momentum.shadow import append_forecast

KLINES_URL = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=1000"


def fetch_klines() -> list:
    req = urllib.request.Request(KLINES_URL, headers={"User-Agent": "rocket-research"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def to_csv_lines(rows: list) -> str:
    return "\n".join(",".join(str(v) for v in r) for r in rows)


def main() -> int:
    from rocket.momentum.bars import parse_kline_csv

    directory = sys.argv[1] if len(sys.argv) > 1 else "artifacts/momentum/shadow"
    now = datetime.now(UTC)
    cutoff_ms = int(now.timestamp() * 1000) // (4 * 3600 * 1000) * (4 * 3600 * 1000)
    try:
        from rocket.momentum import contracts

        raw = fetch_klines()
        rows_1h = parse_kline_csv(
            to_csv_lines(raw), vintage="binance-spot-rest", ingested_at=now.isoformat()
        )
        bars_4h = aggregate_4h(rows_1h)
        hist = contiguous_4h_before(bars_4h, cutoff_ms, min_bars=contracts.SIGMA_BARS + 1)
        if not hist:
            raise ValueError("incomplete 30d history")
        sig = sigma_at(hist)
        state = crossing_state(hist, sigma=sig) if sig else {"UP": "UNKNOWN", "DOWN": "UNKNOWN"}
        feats = tier_a(bars_4h, cutoff_ms, sigma=sig or 0.0)
        candidate_state = {"UP": state["UP"], "DOWN": state["DOWN"], "sigma": sig,
                           "reference_price": hist[-1]["close"]}
        missing = list(feats.get("missing", []))
        features = {k: v for k, v in feats.items() if k not in ("schema", "tier", "missing")}
        fingerprint = f"rest-n{len(rows_1h)}-{rows_1h[-1]['open_ms'] if rows_1h else 'empty'}"
    except Exception as exc:  # UNKNOWN is the contracted fallback.
        candidate_state = {"UP": "UNKNOWN", "DOWN": "UNKNOWN", "error": type(exc).__name__}
        features, missing, fingerprint = {}, ["all"], "unavailable"
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15, check=False
        ).stdout.strip()
    except Exception:
        commit = "unknown"
    decision_time = (datetime.fromtimestamp(cutoff_ms / 1000, UTC) + timedelta(minutes=5)).isoformat()
    record = append_forecast(
        directory,
        decision_time=decision_time,
        cutoff_ms=cutoff_ms,
        candidate_state=candidate_state,
        features=features,
        missing=missing,
        model_output=None,  # No admitted model yet; forecasts are state+features only.
        commit=commit,
        fingerprints={"klines": fingerprint},
    )
    print(json.dumps({"id": record["id"], "decision_time": decision_time,
                      "candidate_state": candidate_state, "missing": missing}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
