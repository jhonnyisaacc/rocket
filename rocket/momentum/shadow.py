"""Append-only prospective journal; no numeric decision depends on an LLM."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from rocket.momentum.core import (
    CONTRACT,
    FEATURE_NAMES,
    FEATURE_SCHEMA,
    CandidateEvent,
    canonical,
    fingerprint,
)

FORECAST_FIELDS = {
    "decision_time",
    "data_cutoff",
    "candidate_state",
    "candidate_direction",
    "candidate_event",
    "code_tree_sha256",
    "features",
    "unknown_features",
    "feature_schema_version",
    "model_version",
    "model_output",
    "candidate_generator_version",
    "label_contract_version",
    "code_commit",
    "source_fingerprints",
    "written_at",
    "collection_mode",
    "availability_policy",
    "source_status",
    "snapshot_id",
}


class ShadowLog:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS forecasts (
                    id TEXT PRIMARY KEY, decision_time INTEGER NOT NULL,
                    collection_mode TEXT NOT NULL, payload TEXT NOT NULL, sha256 TEXT NOT NULL,
                    UNIQUE(decision_time, collection_mode));
                CREATE TABLE IF NOT EXISTS outcomes (
                    id TEXT PRIMARY KEY, forecast_id TEXT NOT NULL REFERENCES forecasts(id),
                    payload TEXT NOT NULL, sha256 TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS forecast_update BEFORE UPDATE ON forecasts
                    BEGIN SELECT RAISE(ABORT, 'forecast is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS forecast_delete BEFORE DELETE ON forecasts
                    BEGIN SELECT RAISE(ABORT, 'forecast is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS outcome_update BEFORE UPDATE ON outcomes
                    BEGIN SELECT RAISE(ABORT, 'outcome is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS outcome_delete BEFORE DELETE ON outcomes
                    BEGIN SELECT RAISE(ABORT, 'outcome is immutable'); END;
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def append_forecast(self, payload: dict) -> str:
        if set(payload) != FORECAST_FIELDS:
            raise ValueError("forecast schema mismatch or forbidden future fields")
        if (
            payload["data_cutoff"] > payload["decision_time"]
            or payload["written_at"] < payload["data_cutoff"]
        ):
            raise ValueError("invalid forecast clocks")
        if (
            payload["feature_schema_version"] != FEATURE_SCHEMA
            or payload["candidate_generator_version"] != CONTRACT
            or payload["label_contract_version"] != CONTRACT
        ):
            raise ValueError("unknown schema/contract identity")
        if set(payload["features"]) != set(FEATURE_NAMES):
            raise ValueError("feature schema keys do not match version")
        if sorted(payload["unknown_features"]) != sorted(
            k for k, v in payload["features"].items() if v is None
        ):
            raise ValueError("unknown feature identity mismatch")
        candidate = payload["candidate_event"]
        if candidate is not None:
            event = CandidateEvent(**candidate)
            if (
                event.decision_time != payload["decision_time"]
                or event.data_cutoff != payload["data_cutoff"]
                or event.direction != payload["candidate_direction"]
                or event.generator != CONTRACT
            ):
                raise ValueError("candidate does not match forecast")
        if payload["model_version"] == "UNTRAINED" and payload["model_output"] is not None:
            raise ValueError("untrained model cannot emit a probability")
        encoded = canonical(payload).decode()
        identity = fingerprint(
            {"decision_time": payload["decision_time"], "mode": payload["collection_mode"]}
        )
        digest = fingerprint(payload)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT sha256 FROM forecasts WHERE id=?", (identity,)).fetchone()
            if previous:
                if previous[0] != digest:
                    raise ValueError("forecast identity already exists with different content")
                return identity
            db.execute(
                "INSERT INTO forecasts VALUES (?,?,?,?,?)",
                (identity, payload["decision_time"], payload["collection_mode"], encoded, digest),
            )
        return identity

    def append_outcome(self, forecast_id: str, payload: dict, now: int) -> str:
        if (
            payload.get("available_at", now + 1) > now
            or payload.get("label_end", now + 1) > now
            or payload.get("contract") != CONTRACT
        ):
            raise ValueError("outcome immature or contract unknown")
        original = self.forecast(forecast_id)
        if payload.get("label_end", 0) <= original["decision_time"]:
            raise ValueError("outcome does not follow forecast")
        identity = fingerprint(
            {
                "forecast": forecast_id,
                "contract": payload["contract"],
                "days": payload["horizon_days"],
                "upper": payload["upper"],
                "lower": payload["lower"],
            }
        )
        digest = fingerprint(payload)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT sha256 FROM outcomes WHERE id=?", (identity,)).fetchone()
            if previous:
                if previous[0] != digest:
                    raise ValueError("outcome amendment requires a distinct version")
                return identity
            db.execute(
                "INSERT INTO outcomes VALUES (?,?,?,?)",
                (identity, forecast_id, canonical(payload).decode(), digest),
            )
        return identity

    def forecast(self, identity: str):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload,sha256 FROM forecasts WHERE id=?", (identity,)
            ).fetchone()
        if not row:
            raise ValueError("unknown forecast")
        payload = json.loads(row[0])
        if fingerprint(payload) != row[1]:
            raise ValueError("forecast integrity failure")
        return payload

    def at_decision(self, decision: int, mode: str):
        with self.connect() as db:
            row = db.execute(
                "SELECT id FROM forecasts WHERE decision_time=? AND collection_mode=?",
                (decision, mode),
            ).fetchone()
        return (row[0], self.forecast(row[0])) if row else None

    def forecasts(self):
        with self.connect() as db:
            rows = db.execute("SELECT id FROM forecasts ORDER BY decision_time,id").fetchall()
        return [(identity, self.forecast(identity)) for (identity,) in rows]
