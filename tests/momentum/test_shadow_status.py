"""Audit stored evidence without creating or rewriting prospective observations."""

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict

import pytest

from rocket.momentum.collect import collect
from rocket.momentum.core import DAY, FOUR_HOURS, HOUR, LAG, canonical, fingerprint, label
from rocket.momentum.enrich import enrich
from rocket.momentum.shadow import ShadowLog
from rocket.momentum.status import _forecast, status
from tests.momentum.test_core import event, forward
from tests.momentum.test_shadow_source import payload


def _mature_candidate(root):
    original = payload()
    original.update(
        candidate_state="ACTIVE",
        candidate_direction=1,
        candidate_event=asdict(event()),
        snapshot_id=event().snapshot_id,
    )
    journal = ShadowLog(root / "shadow.sqlite")
    identity = journal.append_forecast(original)
    raw = json.dumps(
        [
            [i * HOUR, 100, 100, 100, 100, 10, (i + 1) * HOUR - 1, 1000, 1, 5, 500, 0]
            for i in range(1, 7 * 24)
        ]
    ).encode()
    return journal, identity, original, raw


@pytest.mark.parametrize("hour", [0, 4, 8, 12, 16, 20])
def test_six_utc_cutoffs_use_actual_receipt_and_five_minute_decision(tmp_path, hour):
    cutoff = 32 * DAY + hour * HOUR
    times = iter([cutoff + 120_000, cutoff + 121_000])
    collected = collect(
        tmp_path, now_fn=lambda: next(times), fetch=lambda _: b"[]", commit="fixture"
    )
    forecast = collected["forecast"]
    assert forecast["data_cutoff"] == cutoff
    assert forecast["decision_time"] == cutoff + LAG
    assert forecast["written_at"] == cutoff + 121_000
    assert forecast["candidate_state"] == "UNKNOWN"
    audit = status(tmp_path, now=cutoff + LAG)
    assert audit["utc_cutoff_hours"] == [0, 4, 8, 12, 16, 20]
    assert audit["scheduled_decision_lag_ms"] == LAG
    assert audit["forecast_source_blobs_verified"] == 1


def test_missing_scheduled_slots_are_listed_without_backfilling(tmp_path):
    startup = payload()
    startup["collection_mode"] = "startup"
    journal = ShadowLog(tmp_path / "shadow.sqlite")
    journal.append_forecast(startup)
    cutoff = 3 * FOUR_HOURS
    times = iter([cutoff + 120_000, cutoff + 121_000])
    collect(tmp_path, now_fn=lambda: next(times), fetch=lambda _: b"[]", commit="fixture")
    before = (tmp_path / "shadow.sqlite").read_bytes()
    audit = status(tmp_path, now=cutoff + LAG)
    assert audit["missing_scheduled_cutoffs"] == [FOUR_HOURS, 2 * FOUR_HOURS]
    assert audit["scheduled_slots_expected_since_startup"] == 3
    assert audit["forecast_records"] == 2
    assert (tmp_path / "shadow.sqlite").read_bytes() == before


def test_original_v1_startup_remains_auditable_without_new_fields(tmp_path):
    original = payload()
    original.update(feature_schema_version="price-market-v1", collection_mode="startup")
    del original["candidate_event"]
    del original["code_tree_sha256"]
    identity = fingerprint({"decision_time": original["decision_time"], "mode": "startup"})
    journal = ShadowLog(tmp_path / "shadow.sqlite")
    with journal.connect() as db:
        db.execute(
            "INSERT INTO forecasts VALUES (?,?,?,?,?)",
            (
                identity,
                original["decision_time"],
                "startup",
                canonical(original).decode(),
                fingerprint(original),
            ),
        )
    audit = status(tmp_path, now=LAG)
    assert audit["feature_schema_versions"] == ["price-market-v1"]
    assert audit["forecasts_without_code_tree_sha256"] == 1
    assert journal.forecast(identity) == original


def test_source_backed_outcome_replays_and_keeps_forecast_bytes(tmp_path):
    journal, identity, original, raw = _mature_candidate(tmp_path)
    assert enrich(tmp_path, now_fn=lambda: 8 * DAY, fetch=lambda _: raw)["enriched"] == 1
    before = (tmp_path / "shadow.sqlite").read_bytes()
    audit = status(tmp_path, now=8 * DAY)
    assert audit["outcome_source_blobs_verified"] == 1
    assert audit["outcome_records_replayed"] == 1
    assert audit["outcome_receipt_integrity"] == "VERIFIED"
    assert journal.forecast(identity) == original
    assert (tmp_path / "shadow.sqlite").read_bytes() == before


@pytest.mark.parametrize("damage", ["missing", "tampered"])
def test_outcome_source_blob_is_required_and_checksum_checked(tmp_path, damage):
    _, _, _, raw = _mature_candidate(tmp_path)
    enrich(tmp_path, now_fn=lambda: 8 * DAY, fetch=lambda _: raw)
    path = tmp_path / "sources" / f"{hashlib.sha256(raw).hexdigest()}.json"
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="source blob missing or integrity mismatch"):
        status(tmp_path, now=8 * DAY)


def test_payload_hash_alone_cannot_validate_wrong_outcome_against_source(tmp_path):
    journal, identity, _, raw = _mature_candidate(tmp_path)
    from rocket.momentum.collect import store_blob

    outcome = asdict(label(event(), forward()))
    outcome.update(available_at=8 * DAY, source_fingerprint=store_blob(tmp_path, raw), mfe=0.5)
    journal.append_outcome(identity, outcome, 8 * DAY)
    with pytest.raises(ValueError, match="outcome source/label replay mismatch"):
        status(tmp_path, now=8 * DAY)


@pytest.mark.parametrize("receipt", [7 * DAY + LAG - 1, 9 * DAY])
def test_outcome_receipt_must_follow_maturity_and_precede_audit_clock(tmp_path, receipt):
    journal, identity, _, _ = _mature_candidate(tmp_path)
    outcome = asdict(label(event(), forward()))
    outcome["available_at"] = receipt
    journal.append_outcome(identity, outcome, 10 * DAY)
    with pytest.raises(ValueError, match="outcome contract, maturity or receipt mismatch"):
        status(tmp_path, now=8 * DAY)


def test_legacy_synthetic_outcome_does_not_claim_observed_source_parity(tmp_path):
    journal, identity, _, _ = _mature_candidate(tmp_path)
    journal.append_outcome(identity, asdict(label(event(), forward())), 8 * DAY)
    audit = status(tmp_path, now=8 * DAY)
    assert audit["outcome_records_without_source_receipt"] == 1
    assert audit["outcome_records_replayed"] == 0
    assert audit["outcome_receipt_integrity"] == "INCOMPLETE_LEGACY_RECEIPTS"
    assert audit["integrity"] == "PAYLOADS_VERIFIED_RECEIPTS_INCOMPLETE"


def test_audit_does_not_create_a_missing_journal_or_assert_automation_state(tmp_path):
    with pytest.raises(ValueError, match="journal does not exist"):
        status(tmp_path, now=DAY)
    assert not (tmp_path / "shadow.sqlite").exists()
    ShadowLog(tmp_path / "shadow.sqlite")
    assert status(tmp_path, now=DAY)["automation_state"] == "NOT_VERIFIED_BY_JOURNAL_AUDIT"


def _audit_record(record):
    identity = fingerprint(
        {"decision_time": record["decision_time"], "mode": record["collection_mode"]}
    )
    return _forecast(
        identity,
        record["decision_time"],
        record["collection_mode"],
        canonical(record).decode(),
        fingerprint(record),
        DAY,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("feature_schema_version", "price-market-v99"),
        ("candidate_generator_version", "other-generator"),
        ("label_contract_version", "other-label"),
        ("code_commit", ""),
        ("code_commit", "  "),
        ("code_commit", None),
        ("code_tree_sha256", ""),
        ("code_tree_sha256", None),
        ("candidate_state", "OTHER"),
        ("candidate_direction", 1),
        ("decision_time", LAG + 1),
    ],
)
def test_rehashed_payload_cannot_bypass_frozen_identity_and_clock_checks(field, value):
    original = payload()
    original.update(code_commit="a" * 40, code_tree_sha256="b" * 64)
    altered = deepcopy(original)
    altered[field] = value
    with pytest.raises(ValueError):
        _audit_record(altered)
    assert _audit_record(original) == original


@pytest.mark.parametrize(
    "damage",
    [
        "missing_key",
        "extra_key",
        "missing_null_name",
        "duplicate_null_name",
        "unknown_nonnull",
        "filled_null",
    ],
)
def test_rehashed_features_and_unknown_names_must_preserve_packet_identity(damage):
    original = payload()
    original.update(code_commit="a" * 40, code_tree_sha256="b" * 64)
    altered = deepcopy(original)
    if damage == "missing_key":
        del altered["features"]["rv_ratio"]
    elif damage == "extra_key":
        altered["features"]["future_return"] = None
        altered["unknown_features"].append("future_return")
    elif damage == "missing_null_name":
        altered["unknown_features"].remove("rv_ratio")
    elif damage == "duplicate_null_name":
        altered["unknown_features"].append("rv_ratio")
    elif damage == "unknown_nonnull":
        altered["unknown_features"].append("not_a_feature")
    else:
        altered["features"]["rv_ratio"] = 1.5
    with pytest.raises(ValueError, match="feature or missingness"):
        _audit_record(altered)
    assert _audit_record(original) == original


@pytest.mark.parametrize("direction", [None, 0, 2, True])
def test_active_state_requires_exact_signed_direction(direction):
    original = payload()
    original.update(candidate_state="ACTIVE", candidate_direction=direction)
    with pytest.raises(ValueError, match="state/direction"):
        _audit_record(original)


@pytest.mark.parametrize(
    "field,value",
    [
        ("decision_time", LAG + 1),
        ("data_cutoff", 1),
        ("direction", -1),
        ("snapshot_id", "other-snapshot"),
    ],
)
def test_candidate_cannot_diverge_from_forecast_clocks_direction_or_snapshot(field, value):
    original = payload()
    original.update(
        candidate_state="ACTIVE",
        candidate_direction=1,
        candidate_event=asdict(event()),
        snapshot_id=event().snapshot_id,
        code_commit="a" * 40,
        code_tree_sha256="b" * 64,
    )
    altered = deepcopy(original)
    altered["candidate_event"][field] = value
    with pytest.raises(ValueError, match="candidate does not match"):
        _audit_record(altered)
    assert _audit_record(original) == original


def test_v2_requires_code_tree_and_v1_only_may_omit_legacy_fields():
    original = payload()
    original.update(code_commit="a" * 40, code_tree_sha256="b" * 64)
    assert _audit_record(original) == original
    del original["code_tree_sha256"]
    with pytest.raises(ValueError, match="forecast schema mismatch"):
        _audit_record(original)
    original["feature_schema_version"] = "price-market-v1"
    assert _audit_record(original) == original
    del original["candidate_event"]
    assert _audit_record(original) == original
