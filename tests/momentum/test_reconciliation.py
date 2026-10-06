import json
import math
from collections import Counter
from pathlib import Path

import pytest

from rocket.momentum.core import DAY, HOUR, LAG, Bar, CandidateEvent, fingerprint, label

ROOT = Path(__file__).resolve().parents[2] / "docs/research/momentum"


def test_frozen_labels_and_all_replication_identities_agree():
    events = json.loads((ROOT / "results/EVENTS.json").read_text())
    frozen = json.loads((ROOT / "reconciliation/PR49_FROZEN_CENSUS.json").read_text())
    comparison = json.loads((ROOT / "reconciliation/CANDIDATE_DIFF.json").read_text())
    assert fingerprint([row["label"] for row in events]) == frozen["labels_fingerprint"]
    assert len(comparison) == len(events) == 354
    for row, original in zip(comparison, events):
        assert row["event_id"] == original["event"]["event_id"]
        assert row["globally_spaced"] == original["independent"]
        for key, value in row["canonical"].items():
            assert value == original["label"][key]
        assert row["canonical_reference_price"] == row["muse_reference_price"]
        assert row["canonical_scale_S"] == pytest.approx(row["muse_scale_S"], abs=1e-12)
        assert set(row["orientation_only_discrepant_fields"]) <= {"mfe", "mfe_normalized"}
    assert Counter(row["label"]["outcome"] for row in events if row["independent"]) == {
        "CONTINUES_UP": 5,
        "CONTINUES_DOWN": 8,
        "FAILS": 42,
        "TIMEOUT": 46,
        "UNKNOWN": 6,
    }


def test_eighth_down_success_uses_the_hourly_low():
    traces = json.loads((ROOT / "reconciliation/DISCREPANT_BARRIER_TRACES.json").read_text())
    trace = next(r for r in traces if r["cutoff_utc"] == "2025-11-13T20:00:00+00:00")
    candidate = next(
        r["event"]
        for r in json.loads((ROOT / "results/EVENTS.json").read_text())
        if r["event"]["event_id"] == trace["event_id"]
    )
    event = CandidateEvent(**candidate)
    touch = trace["first_touch"]
    assert event.reference_price == 98682.14
    assert event.scale == pytest.approx(0.06343520457967326)
    assert touch["low"] < trace["favorable_price_barrier"] < touch["high"]
    assert touch["high"] < trace["adverse_price_barrier"]
    assert -math.log(touch["low"] / event.reference_price) >= 2 * event.scale
    assert -math.log(touch["high"] / event.reference_price) < 2 * event.scale
    rows = [
        Bar(
            t,
            t + HOUR,
            t + HOUR + LAG,
            0,
            event.reference_price,
            event.reference_price,
            event.reference_price,
            event.reference_price,
            0,
        )
        for t in range(event.data_cutoff + HOUR, event.data_cutoff + 7 * DAY, HOUR)
    ]
    from datetime import datetime

    t = int(datetime.fromisoformat(touch["open_utc"]).timestamp() * 1000)
    index = (t - event.data_cutoff) // HOUR - 1
    rows[index] = Bar(
        t,
        t + HOUR,
        t + HOUR + LAG,
        0,
        touch["open"],
        touch["high"],
        touch["low"],
        touch["close"],
        0,
    )
    result = label(event, rows)
    assert result.outcome == "CONTINUES_DOWN"
    assert result.barrier_time == t + HOUR
