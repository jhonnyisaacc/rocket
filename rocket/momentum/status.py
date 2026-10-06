"""Audit immutable forecast/source integrity and expected scheduled coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from rocket.momentum.collect import clock_ms, parse_live
from rocket.momentum.core import (
    CONTRACT,
    DAY,
    FEATURE_NAMES,
    FEATURE_SCHEMA,
    FOUR_HOURS,
    LAG,
    CandidateEvent,
    fingerprint,
    label,
)
from rocket.momentum.shadow import FORECAST_FIELDS


def _source_blob(root: Path, digest: str):
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(c not in "0123456789abcdef" for c in digest)
    ):
        raise ValueError("invalid source fingerprint")
    path = root / "sources" / f"{digest}.json"
    if not path.exists():
        raise ValueError("source blob missing or integrity mismatch")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("source blob missing or integrity mismatch")
    return raw


def _forecast(identity, indexed_decision, indexed_mode, raw, digest, now):
    record = json.loads(raw)
    if fingerprint(record) != digest:
        raise ValueError("forecast integrity failure")
    fields = set(record)
    expected = FORECAST_FIELDS
    if record.get("feature_schema_version") == "price-market-v1":
        # The original real startup predates these fields. Audit, never retrofit it.
        expected = FORECAST_FIELDS - {"candidate_event", "code_tree_sha256"}
    if not expected <= fields <= FORECAST_FIELDS:
        raise ValueError("forecast schema mismatch or forbidden future fields")
    if (
        record["feature_schema_version"] not in {"price-market-v1", FEATURE_SCHEMA}
        or record["candidate_generator_version"] != CONTRACT
        or record["label_contract_version"] != CONTRACT
    ):
        raise ValueError("unknown forecast schema/contract identity")
    if (
        not isinstance(record["features"], dict)
        or not isinstance(record["unknown_features"], list)
        or set(record["features"]) != set(FEATURE_NAMES)
        or sorted(record["unknown_features"])
        != sorted(name for name, value in record["features"].items() if value is None)
    ):
        raise ValueError("forecast feature or missingness identity mismatch")
    if not isinstance(record["code_commit"], str) or not record["code_commit"].strip():
        raise ValueError("forecast code commit identity missing")
    if "code_tree_sha256" in record and (
        not isinstance(record["code_tree_sha256"], str) or not record["code_tree_sha256"].strip()
    ):
        raise ValueError("forecast code tree identity missing")
    state, direction = record["candidate_state"], record["candidate_direction"]
    if (
        state not in {"UNKNOWN", "NO_CANDIDATE", "ACTIVE"}
        or (state == "ACTIVE" and (type(direction) is not int or direction not in (-1, 1)))
        or (state != "ACTIVE" and direction is not None)
    ):
        raise ValueError("forecast state/direction mismatch")
    if (
        indexed_decision != record["decision_time"]
        or indexed_mode != record["collection_mode"]
        or identity != fingerprint({"decision_time": indexed_decision, "mode": indexed_mode})
    ):
        raise ValueError("forecast identity or indexed clock mismatch")
    cutoff, decision, written = record["data_cutoff"], record["decision_time"], record["written_at"]
    if (
        any(type(t) is not int for t in (cutoff, decision, written))
        or cutoff < 0
        or cutoff % FOUR_HOURS
        or cutoff + LAG > decision
        or cutoff > written
        or written > now
    ):
        raise ValueError("invalid forecast receipt/cutoff clocks")
    if indexed_mode == "scheduled":
        if decision != cutoff + LAG:
            raise ValueError("scheduled decision does not match UTC 4h clock")
    elif indexed_mode == "startup":
        if decision != written:
            raise ValueError("startup decision is not the actual receipt")
    else:
        raise ValueError("unknown collection mode")
    if record["source_status"] == "OK" and written > decision:
        raise ValueError("source received after decision cannot be OK")
    candidate = record.get("candidate_event")
    if candidate is not None:
        if state != "ACTIVE":
            raise ValueError("candidate event requires ACTIVE state")
        event = CandidateEvent(**candidate)
        if (
            event.decision_time != decision
            or event.data_cutoff != cutoff
            or event.direction != record["candidate_direction"]
            or event.snapshot_id != record["snapshot_id"]
            or event.generator != CONTRACT
        ):
            raise ValueError("candidate does not match original forecast")
    if record["model_version"] == "UNTRAINED" and record["model_output"] is not None:
        raise ValueError("untrained model cannot emit a forecast")
    return record


def status(root: Path, now: int | None = None):
    now = clock_ms() if now is None else now
    path = root / "shadow.sqlite"
    if not path.is_file():
        raise ValueError("shadow journal does not exist; audit cannot create a startup")
    # Auditing is read-only, including schema and triggers.
    with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as db:
        forecast_rows = db.execute(
            "SELECT id,decision_time,collection_mode,payload,sha256 "
            "FROM forecasts ORDER BY decision_time,id"
        ).fetchall()
        rows = db.execute(
            "SELECT id,forecast_id,payload,sha256 FROM outcomes ORDER BY id"
        ).fetchall()
        triggers = {
            name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        }
    expected_triggers = {"forecast_update", "forecast_delete", "outcome_update", "outcome_delete"}
    if not expected_triggers <= triggers:
        raise ValueError("shadow immutable trigger missing")
    records = [(i, _forecast(i, d, m, raw, sha, now)) for i, d, m, raw, sha in forecast_rows]
    originals = dict(records)
    blobs = set()
    forecast_blobs = set()
    for _, record in records:
        for digest in record["source_fingerprints"].values():
            if digest is None:
                continue
            _source_blob(root, digest)
            blobs.add(digest)
            forecast_blobs.add(digest)
    first_cutoff = min((r["data_cutoff"] for _, r in records), default=None)
    scheduled = {r["data_cutoff"] for _, r in records if r["collection_mode"] == "scheduled"}
    expected = (
        list(range(first_cutoff + FOUR_HOURS, now // FOUR_HOURS * FOUR_HOURS + 1, FOUR_HOURS))
        if first_cutoff is not None
        else []
    )
    expected = [t for t in expected if t + LAG <= now]
    outcome_blobs = set()
    without_receipt, replayed = 0, 0
    for identity, forecast_id, raw, digest in rows:
        outcome = json.loads(raw)
        if fingerprint(outcome) != digest:
            raise ValueError("outcome integrity mismatch")
        if forecast_id not in originals:
            raise ValueError("outcome refers to unknown forecast")
        original = originals[forecast_id]
        if (
            outcome.get("contract") != CONTRACT
            or outcome.get("horizon_days") not in (3, 7, 14)
            or outcome["label_end"] != original["data_cutoff"] + outcome["horizon_days"] * DAY
            or not outcome["label_end"] + LAG <= outcome["available_at"] <= now
        ):
            raise ValueError("outcome contract, maturity or receipt mismatch")
        if identity != fingerprint(
            {
                "forecast": forecast_id,
                "contract": outcome["contract"],
                "days": outcome["horizon_days"],
                "upper": outcome["upper"],
                "lower": outcome["lower"],
            }
        ):
            raise ValueError("outcome identity mismatch")
        source = outcome.get("source_fingerprint")
        if source is None:
            # Legacy synthetic labels have no observed bytes. Never assert receipt parity for them.
            without_receipt += 1
            continue
        future = _source_blob(root, source)
        blobs.add(source)
        outcome_blobs.add(source)
        candidate = original.get("candidate_event")
        if candidate is None:
            raise ValueError("source-backed outcome has no original candidate")
        event = CandidateEvent(**candidate)
        if (
            event.decision_time != original["decision_time"]
            or event.data_cutoff != original["data_cutoff"]
            or event.direction != original["candidate_direction"]
            or event.generator != CONTRACT
        ):
            raise ValueError("outcome candidate does not match original forecast")
        expected_outcome = asdict(
            label(
                event,
                parse_live(future, outcome["available_at"]),
                days=outcome["horizon_days"],
                upper=outcome["upper"],
                lower=outcome["lower"],
            )
        )
        expected_outcome["available_at"] = outcome["available_at"]
        expected_outcome["source_fingerprint"] = source
        if expected_outcome != outcome:
            raise ValueError("outcome source/label replay mismatch")
        replayed += 1
    return {
        "audited_at": now,
        "forecast_records": len(records),
        "outcome_records": len(rows),
        "source_blobs_verified": len(blobs),
        "forecast_source_blobs_verified": len(forecast_blobs),
        "outcome_source_blobs_verified": len(outcome_blobs),
        "outcome_records_replayed": replayed,
        "outcome_records_without_source_receipt": without_receipt,
        "outcome_receipt_integrity": (
            "INCOMPLETE_LEGACY_RECEIPTS"
            if without_receipt
            else "VERIFIED"
            if rows
            else "PENDING_NO_OUTCOMES"
        ),
        "forecast_ids": [i for i, _ in records],
        "first_decision_time": min((r["decision_time"] for _, r in records), default=None),
        "latest_decision_time": max((r["decision_time"] for _, r in records), default=None),
        "scheduled_slots_expected_since_startup": len(expected),
        "scheduled_slots_recorded": len(scheduled),
        "missing_scheduled_cutoffs": [t for t in expected if t not in scheduled],
        "source_states": [r["source_status"] for _, r in records],
        "model_versions": sorted({r["model_version"] for _, r in records}),
        "feature_schema_versions": sorted({r["feature_schema_version"] for _, r in records}),
        "code_commits": sorted({r["code_commit"] for _, r in records}),
        "forecasts_without_code_tree_sha256": sum("code_tree_sha256" not in r for _, r in records),
        "utc_cutoff_hours": [0, 4, 8, 12, 16, 20],
        "scheduled_decision_lag_ms": LAG,
        "integrity": "PAYLOADS_VERIFIED_RECEIPTS_INCOMPLETE" if without_receipt else "VERIFIED",
        "immutable_triggers_verified": sorted(expected_triggers),
        "automation_id": "btc-momentum-prospective-shadow",
        "automation_state": "NOT_VERIFIED_BY_JOURNAL_AUDIT",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = status(args.root)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
