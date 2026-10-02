"""Capture actual source receipts and deterministic snapshots; never backdate forecasts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import urllib.request
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from rocket.momentum.core import (
    CONTRACT,
    DAY,
    FEATURE_SCHEMA,
    FOUR_HOURS,
    HOUR,
    LAG,
    Bar,
    CandidateEvent,
    aggregate_four_hours,
    fingerprint,
    snapshot,
)
from rocket.momentum.shadow import ShadowLog

ENDPOINT = "https://api.binance.com/api/v3/klines"


def clock_ms():
    return int(datetime.now(UTC).timestamp() * 1000)


def store_blob(root: Path, raw: bytes):
    digest = hashlib.sha256(raw).hexdigest()
    path = root / "sources" / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError("source digest collision")
    return digest


def parse_live(raw: bytes, receipt: int):
    result = []
    for row in json.loads(raw):
        if len(row) != 12 or int(row[6]) != int(row[0]) + HOUR - 1:
            raise ValueError("live source timestamp/schema mismatch")
        if int(row[0]) + HOUR > receipt:
            continue
        result.append(Bar(int(row[0]), int(row[0]) + HOUR, receipt, receipt, *map(float, row[1:6])))
    return result


def collect(root: Path, *, mode="scheduled", now_fn=clock_ms, fetch=None, commit=None):
    started = now_fn()
    cutoff = started // FOUR_HOURS * FOUR_HOURS
    planned = cutoff + LAG
    if mode not in {"startup", "scheduled"}:
        raise ValueError("unknown collection mode")
    journal = ShadowLog(root / "shadow.sqlite")
    existing = journal.at_decision(planned, mode) if mode == "scheduled" else None
    if existing:
        return {"forecast_id": existing[0], "forecast": existing[1]}

    status = "OK"
    digest = None
    bars = []
    try:
        url = (
            f"{ENDPOINT}?symbol=BTCUSDT&interval=1h&limit=1000"
            f"&startTime={cutoff - 32 * DAY}&endTime={cutoff - 1}"
        )
        if fetch is None:
            request = urllib.request.Request(
                url, headers={"User-Agent": "rocket-momentum-shadow/1"}
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
        else:
            raw = fetch(url)
        receipt = now_fn()
        digest = store_blob(root, raw)
        bars = aggregate_four_hours(parse_live(raw, receipt))
    except Exception as exc:
        receipt = now_fn()
        status = f"UNKNOWN_SOURCE_{type(exc).__name__}"
    decision = planned if mode == "scheduled" else receipt
    if receipt > decision:
        status = "UNKNOWN_LATE_RECEIPT"
        bars = []
    view = snapshot(bars, decision, cutoff, prospective=True)
    candidate = None
    if view.direction:
        previous = snapshot(bars, decision, cutoff - FOUR_HOURS, prospective=True)
        if previous.state != "UNKNOWN" and previous.direction != view.direction:
            key = {"cutoff": cutoff, "direction": view.direction, "generator": CONTRACT}
            candidate = asdict(
                CandidateEvent(
                    fingerprint(key),
                    decision,
                    cutoff,
                    view.direction,
                    view.reference_price,
                    view.sigma * math.sqrt(42),
                    view.identity,
                )
            )
    code_tree = fingerprint(
        {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))
        }
    )
    if commit is None:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
            commit += ":DIRTY"
    payload = {
        "decision_time": decision,
        "data_cutoff": cutoff,
        "candidate_state": view.state,
        "candidate_direction": view.direction,
        "candidate_event": candidate,
        "code_tree_sha256": code_tree,
        "features": view.values,
        "unknown_features": list(view.unknown),
        "feature_schema_version": FEATURE_SCHEMA,
        "model_version": "UNTRAINED",
        "model_output": None,
        "candidate_generator_version": CONTRACT,
        "label_contract_version": CONTRACT,
        "code_commit": commit,
        "source_fingerprints": {"binance_spot_1h": digest},
        "written_at": receipt,
        "collection_mode": mode,
        "availability_policy": "ACTUAL_RECEIPT",
        "source_status": status,
        "snapshot_id": view.identity,
    }
    identity = journal.append_forecast(payload)
    return {"forecast_id": identity, "forecast": payload}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--startup", action="store_true")
    args = parser.parse_args()
    print(json.dumps(collect(args.root, mode="startup" if args.startup else "scheduled"), indent=2))
