"""Prospective shadow log: append-only forecast records + separate outcomes.

At each scheduled decision time append ONE JSON record per line with no
future outcome fields. Outcome enrichment appends to a SEPARATE file
keyed by record id and never rewrites the forecast file (verified by
stored sha256). Records carry decision_time, data_cutoff, candidate
state, feature vector, missing list, schema/model/generator/label
versions, code commit and source fingerprints.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime

from rocket.momentum import contracts

FORECAST_FILENAME = "shadow_forecasts.jsonl"
OUTCOME_FILENAME = "shadow_outcomes.jsonl"


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_id(decision_time: str, cutoff_ms: int) -> str:
    return hashlib.sha256(f"{decision_time}|{cutoff_ms}".encode()).hexdigest()[:32]


def append_forecast(
    directory: str,
    *,
    decision_time: str,
    cutoff_ms: int,
    candidate_state: dict,
    features: dict,
    missing: list[str],
    model_output: float | None,
    commit: str,
    fingerprints: dict,
) -> dict:
    """Append a forecast record. Raises if any outcome key is present."""
    for banned in ("outcome", "success", "mfe", "mae", "resolved", "label"):
        if banned in candidate_state or banned in features:
            raise ValueError(f"forecast record must not contain outcome field: {banned}")
    record = {
        "id": record_id(decision_time, cutoff_ms),
        "decision_time": decision_time,
        "data_cutoff_ms": cutoff_ms,
        "candidate_state": candidate_state,
        "features": features,
        "missing": sorted(missing),
        "feature_schema": contracts.FEATURE_SCHEMA_VERSION,
        "model": contracts.MODEL_VERSION,
        "candidate_generator": contracts.CANDIDATE_GENERATOR_VERSION,
        "label_contract": contracts.LABEL_CONTRACT_VERSION,
        "commit": commit,
        "fingerprints": fingerprints,
        "model_output": model_output,
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, FORECAST_FILENAME)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def append_outcome(directory: str, *, record: dict, outcome: dict) -> dict:
    """Enrich in the separate outcome file. Never touches the forecast file."""
    forecast_path = os.path.join(directory, FORECAST_FILENAME)
    before = _sha256_file(forecast_path) if os.path.exists(forecast_path) else None
    entry = {
        "id": record["id"],
        "decision_time": record["decision_time"],
        "outcome": outcome,
        "enriched_at": datetime.now(UTC).isoformat(),
        "forecast_sha256": before,
    }
    with open(os.path.join(directory, OUTCOME_FILENAME), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    after = _sha256_file(forecast_path) if os.path.exists(forecast_path) else None
    if before != after:
        raise RuntimeError("forecast file changed during enrichment")
    return entry


def read_forecasts(directory: str) -> list[dict]:
    path = os.path.join(directory, FORECAST_FILENAME)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def verify_log(directory: str) -> dict:
    """Monotonic ids/decisions, no outcome fields, enrichment joinable."""
    forecasts = read_forecasts(directory)
    seen, ok = set(), True
    for rec in forecasts:
        if rec["id"] in seen:
            ok = False
        seen.add(rec["id"])
        for banned in ("outcome", "success", "mfe", "mae"):
            if banned in rec.get("candidate_state", {}) or banned in rec.get("features", {}):
                ok = False
    out_path = os.path.join(directory, OUTCOME_FILENAME)
    n_outcomes = 0
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    n_outcomes += 1
    return {"n_forecasts": len(forecasts), "n_outcomes": n_outcomes,
            "monotonic_unique": ok, "forecast_sha256": _sha256_file(os.path.join(directory, FORECAST_FILENAME)) if forecasts else None}
