import csv
import io
import json
import sqlite3
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from rocket.momentum.collect import collect
from rocket.momentum.core import (
    CONTRACT,
    DAY,
    FEATURE_NAMES,
    FEATURE_SCHEMA,
    HOUR,
    LAG,
    fingerprint,
    label,
)
from rocket.momentum.shadow import FORECAST_FIELDS, ShadowLog
from rocket.momentum.source import parse_archive
from tests.momentum.test_core import event, forward


def payload():
    return {
        "decision_time": LAG,
        "data_cutoff": 0,
        "candidate_state": "UNKNOWN",
        "candidate_direction": None,
        "candidate_event": None,
        "code_tree_sha256": "fixture",
        "features": dict.fromkeys(FEATURE_NAMES),
        "unknown_features": list(FEATURE_NAMES),
        "feature_schema_version": FEATURE_SCHEMA,
        "model_version": "UNTRAINED",
        "model_output": None,
        "candidate_generator_version": CONTRACT,
        "label_contract_version": CONTRACT,
        "code_commit": "fixture",
        "source_fingerprints": {},
        "written_at": LAG,
        "collection_mode": "scheduled",
        "availability_policy": "ACTUAL_RECEIPT",
        "source_status": "UNKNOWN",
        "snapshot_id": "fixture",
    }


def test_forecast_idempotence_conflict_future_fields_and_integrity(tmp_path):
    log = ShadowLog(tmp_path / "shadow.sqlite")
    p = payload()
    assert set(p) == FORECAST_FIELDS
    identity = log.append_forecast(p)
    assert log.append_forecast(p) == identity
    assert log.forecast(identity) == p
    with pytest.raises(ValueError):
        log.append_forecast(dict(p, candidate_state="ACTIVE"))
    with pytest.raises(ValueError):
        log.append_forecast(dict(p, outcome="FAILS"))
    with pytest.raises(ValueError):
        log.append_forecast(dict(p, model_output=0.9))
    with log.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE forecasts SET payload=? WHERE id=?", ("{}", identity))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM forecasts")


def test_outcome_enrichment_cannot_rewrite_original_or_mature_early(tmp_path):
    log = ShadowLog(tmp_path / "shadow.sqlite")
    p = payload()
    identity = log.append_forecast(p)
    future = asdict(label(event(), forward()))
    with pytest.raises(ValueError):
        log.append_outcome(identity, future, DAY)
    oid = log.append_outcome(identity, future, 8 * DAY)
    assert log.append_outcome(identity, future, 8 * DAY) == oid
    assert fingerprint(log.forecast(identity)) == fingerprint(p)
    with log.connect() as db, pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE outcomes SET payload=?", ("{}",))


def test_collector_actual_receipt_unknown_late_and_blob(tmp_path):
    now = 32 * DAY + 2 * 60_000
    times = iter([now, now + 1000])
    result = collect(
        tmp_path, now_fn=lambda: next(times), fetch=lambda url: b"[]", commit="fixture"
    )
    assert result["forecast"]["decision_time"] == 32 * DAY + LAG
    assert result["forecast"]["candidate_state"] == "UNKNOWN"
    assert result["forecast"]["model_output"] is None
    assert list((tmp_path / "sources").glob("*.json"))
    times = iter([36 * DAY + LAG + 1000, 36 * DAY + LAG + 2000])
    result = collect(
        tmp_path, now_fn=lambda: next(times), fetch=lambda url: b"[]", commit="fixture"
    )
    assert result["forecast"]["source_status"] == "UNKNOWN_LATE_RECEIPT"


@pytest.mark.parametrize("year", [2024, 2025])
def test_archive_units_partial_bars_and_gaps(year):
    factor = 1000 if year >= 2025 else 1
    start = int(datetime(year, 1, 1, tzinfo=UTC).timestamp() * 1000)
    rows = []
    for index in (0, 1, 3):
        t = start + index * HOUR
        rows.append(
            [t * factor, 100, 100, 100, 100, 10, (t + HOUR) * factor - 1, 1000, 1, 5, 500, 0]
        )
    rows[1][6] -= 10
    text = io.StringIO()
    csv.writer(text).writerows(rows)
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(f"BTCUSDT-1h-{year}-01.csv", text.getvalue())
    rejected = []
    bars = parse_archive(data.getvalue(), year, 1, 0, rejected)
    assert [b.open_time for b in bars] == [start, start + 3 * HOUR]
    assert rejected[0]["reason"] == "NONSTANDARD_CLOSE_TIMESTAMP"
    assert bars[0].available_at == start + HOUR + LAG
    assert bars[0].ingested_at == 0


def test_failure_record_persists_without_future_outcomes(tmp_path):
    times = iter([32 * DAY + 2 * 60_000, 32 * DAY + 3 * 60_000])

    def fail(url):
        raise OSError("fixture")

    result = collect(tmp_path, now_fn=lambda: next(times), fetch=fail, commit="fixture")
    assert result["forecast"]["source_status"] == "UNKNOWN_SOURCE_OSError"
    assert result["forecast"]["source_fingerprints"]["binance_spot_1h"] is None
    assert "outcome" not in json.dumps(result["forecast"])


def test_scheduled_retry_returns_original_without_refetch(tmp_path):
    now = 32 * DAY + 2 * 60_000
    times = iter([now, now + 1000])
    first = collect(tmp_path, now_fn=lambda: next(times), fetch=lambda url: b"[]", commit="one")

    def forbid(url):
        raise AssertionError("retry must not fetch a new vintage")

    second = collect(tmp_path, now_fn=lambda: now + 2000, fetch=forbid, commit="two")
    assert second == first


def test_enrichment_process_replays_mature_candidate_and_preserves_forecast(tmp_path):
    from rocket.momentum.enrich import enrich

    log = ShadowLog(tmp_path / "shadow.sqlite")
    p = payload()
    p["candidate_state"] = "ACTIVE"
    p["candidate_direction"] = 1
    p["candidate_event"] = asdict(event())
    identity = log.append_forecast(p)
    data = [
        [i * HOUR, 100, 100, 100, 100, 10, (i + 1) * HOUR - 1, 1000, 1, 5, 500, 0]
        for i in range(1, 7 * 24)
    ]
    result = enrich(tmp_path, now_fn=lambda: 8 * DAY, fetch=lambda url: json.dumps(data).encode())
    assert result == {"enriched": 1, "pending": 0, "forecast_updates": 0}
    assert log.forecast(identity) == p
    assert enrich(tmp_path, now_fn=lambda: 8 * DAY, fetch=lambda url: b"[]")["enriched"] == 0


def test_collector_numeric_crossing_matches_historical_generator(tmp_path):
    import math

    from rocket.momentum.collect import parse_live
    from rocket.momentum.core import aggregate_four_hours, candidates

    cutoff = 32 * DAY
    begin = cutoff - 32 * DAY
    rows = []
    for i in range(32 * 24):
        t = begin + i * HOUR
        p = 100 + math.sin(i // 4) * 0.2 if i < 32 * 24 - 4 else 110.0
        rows.append([t, p, p, p, p, 10, t + HOUR - 1, 1000, 1, 5, 500, 0])
    raw = json.dumps(rows).encode()
    times = iter([cutoff + 120000, cutoff + 121000])
    result = collect(tmp_path, now_fn=lambda: next(times), fetch=lambda url: raw, commit="fixture")
    candidate = result["forecast"]["candidate_event"]
    assert candidate is not None
    historical = [
        __import__("dataclasses").replace(b, available_at=b.end_time + LAG)
        for b in aggregate_four_hours(parse_live(raw, cutoff + 121000))
    ]
    old, _ = candidates(historical)
    assert old[-1].event_id == candidate["event_id"]
    assert candidate["decision_time"] == cutoff + LAG
    assert candidate["scale"] == pytest.approx(old[-1].scale)


def test_collector_dirty_tree_has_exact_hash_and_forecast_unknowns(tmp_path):
    times = iter([32 * DAY + 120000, 32 * DAY + 121000])
    result = collect(
        tmp_path, now_fn=lambda: next(times), fetch=lambda url: b"[]", commit="fixture:DIRTY"
    )
    assert len(result["forecast"]["code_tree_sha256"]) == 64
    assert result["forecast"]["model_output"] is None


def test_nested_future_feature_or_candidate_field_is_rejected(tmp_path):
    log = ShadowLog(tmp_path / "shadow.sqlite")
    p = payload()
    with pytest.raises(ValueError):
        log.append_forecast(dict(p, features=dict(p["features"], future_return=0.5)))
    bad = asdict(event())
    bad["outcome"] = "CONTINUES_UP"
    with pytest.raises(TypeError):
        log.append_forecast(dict(p, candidate_event=bad))


def test_status_detects_blob_tampering_and_missing_scheduled_slots(tmp_path):
    from rocket.momentum.status import status

    p = payload()
    log = ShadowLog(tmp_path / "shadow.sqlite")
    log.append_forecast(p)
    result = status(tmp_path, now=DAY)
    assert result["missing_scheduled_cutoffs"]
    assert result["integrity"] == "VERIFIED"
    from rocket.momentum.collect import store_blob

    digest = store_blob(tmp_path, b"[]")
    p["decision_time"] += DAY
    p["data_cutoff"] += DAY
    p["written_at"] += DAY
    p["source_fingerprints"] = {"fixture": digest}
    log.append_forecast(p)
    (tmp_path / "sources" / f"{digest}.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        status(tmp_path, now=2 * DAY)
