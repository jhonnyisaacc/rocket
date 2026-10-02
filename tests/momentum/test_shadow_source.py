import csv
import io
import json
import sqlite3
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from rocket.momentum.collect import collect
from rocket.momentum.core import CONTRACT, DAY, FEATURE_SCHEMA, HOUR, LAG, fingerprint, label
from rocket.momentum.shadow import FORECAST_FIELDS, ShadowLog
from rocket.momentum.source import parse_archive
from tests.momentum.test_core import event, forward


def payload():
    return {
        "decision_time": LAG,
        "data_cutoff": 0,
        "candidate_state": "UNKNOWN",
        "candidate_direction": None,
        "features": {"x": None},
        "unknown_features": ["x"],
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
