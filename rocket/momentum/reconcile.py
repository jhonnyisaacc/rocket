"""Offline MOM-000 replication audit against pinned PR #50; never fits a predictor."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import subprocess
import sys
import types
import zipfile
from bisect import bisect_left
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rocket.momentum.census import segment_legs
from rocket.momentum.core import (
    DAY,
    FOUR_HOURS,
    HOUR,
    aggregate_four_hours,
    candidates,
    dt,
    fingerprint,
    interval_groups,
    label,
    spaced_events,
)
from rocket.momentum.source import load

MUSE_COMMIT = "b8ddbd0d1f477f82f96b26298885b97b0f95e063"
CODEX_COMMIT = "c8f22be5a7f065382d01d4fa167a0b9eacdb67c3"
MODULES = ("contracts", "bars", "candidates", "labels", "episodes", "metrics", "census")


def git_file(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"])


def replica():
    """Load only descriptive modules in an isolated namespace; hash original bytes."""
    package = types.ModuleType("_momentum_muse_replica")
    package.__path__ = []
    sys.modules[package.__name__] = package
    hashes = {}
    for name in MODULES:
        raw = git_file(MUSE_COMMIT, f"rocket/momentum/{name}.py")
        hashes[name] = hashlib.sha256(raw).hexdigest()
        module = types.ModuleType(f"{package.__name__}.{name}")
        sys.modules[module.__name__] = module
        setattr(package, name, module)
        source = raw.decode().replace("rocket.momentum", package.__name__)
        exec(compile(source, f"PR50@{MUSE_COMMIT}/{name}.py", "exec"), module.__dict__)  # noqa: S102 - only pinned, audited descriptive source
    # A separately named diagnostic variant changes only the signed OHLC orientation.
    source = git_file(MUSE_COMMIT, "rocket/momentum/labels.py").decode()
    assert source.count('math.log(bar["high"])') == 1
    assert source.count('math.log(bar["low"])') == 1
    source = source.replace(
        'math.log(bar["high"])', 'math.log(bar["high"] if sign == 1 else bar["low"])'
    )
    source = source.replace(
        'math.log(bar["low"]) - ref', 'math.log(bar["low"] if sign == 1 else bar["high"]) - ref'
    )
    source = source.replace('math.log(b["high"])', 'math.log(b["high"] if sign == 1 else b["low"])')
    source = source.replace(
        'math.log(b["low"]) - ref', 'math.log(b["low"] if sign == 1 else b["high"]) - ref'
    )
    fixed = types.ModuleType(f"{package.__name__}.labels_orientation_diagnostic")
    exec(  # noqa: S102 - pinned label diagnostic, no predictor
        compile(
            source.replace("rocket.momentum", package.__name__),
            "PR50_orientation_only_diagnostic",
            "exec",
        ),
        fixed.__dict__,
    )
    return package, fixed, hashes


def normalize_muse(event, outcome):
    side = event["direction"]
    return {
        "outcome": f"CONTINUES_{side}" if outcome["outcome"] == "CONTINUES" else outcome["outcome"],
        "barrier_time": outcome["resolved_ms"] + HOUR
        if outcome["resolved_ms"] is not None
        else None,
        "mfe": outcome["mfe_log"],
        "mae": outcome["mae_log"],
        "mfe_normalized": outcome["mfe_S"],
        "mae_normalized": outcome["mae_S"],
        "signed_return": outcome["end_log"],
    }


def different(left, right):
    fields = []
    for key, value in left.items():
        other = right[key]
        equal = (
            math.isclose(value, other, rel_tol=1e-12, abs_tol=1e-12)
            if isinstance(value, float) and isinstance(other, float)
            else value == other
        )
        if not equal:
            fields.append(key)
    return fields


def source_taxonomy(raw_rows, accepted, bars, eligible, quarantine):
    first = int(dt(accepted[0].open_time).replace(month=1, day=1, hour=0).timestamp() * 1000)
    end = int(dt(accepted[-1].end_time).timestamp() * 1000)
    present = {r["open_time"] for r in raw_rows}
    valid = {b.open_time for b in accepted}
    missing = [t for t in range(first, end, HOUR) if t not in present]
    unusable = [t for t in range(first, end, HOUR) if t not in valid]
    accepted_4h = {b.end_time for b in bars}
    incomplete = [
        t + FOUR_HOURS for t in range(first, end, FOUR_HOURS) if t + FOUR_HOURS not in accepted_4h
    ]
    details = []
    for row in raw_rows:
        if row["open_time"] in valid:
            continue
        detail = dict(row)
        detail["open_utc"] = dt(row["open_time"]).isoformat()
        detail["vendor_close_delta_from_ideal_ms"] = row["close_time_ms"] - (
            row["open_time"] + HOUR - 1
        )
        detail["category"] = (
            "CLOSE_PRECEDES_OPEN"
            if row["close_time_ms"] < row["open_time"]
            else "NONSTANDARD_CLOSE_TIMESTAMP"
        )
        details.append(detail)
    expected_4h = (end - first) // FOUR_HOURS
    return {
        "expected_hourly_slots": (end - first) // HOUR,
        "received_vendor_rows": len(raw_rows),
        "accepted_hourly_rows": len(accepted),
        "malformed_column_numeric_ohlc_rows": 0,
        "quarantined_rows": len(quarantine),
        "nonstandard_close_timestamp_rows": len(details),
        "close_before_open_rows": sum(r["category"] == "CLOSE_PRECEDES_OPEN" for r in details),
        "invalid_open_alignment_or_unit_rows": 0,
        "duplicate_open_rows": len(raw_rows) - len(present),
        "missing_expected_vendor_hours": len(missing),
        "unusable_expected_hours": len(unusable),
        "expected_4h_groups": expected_4h,
        "complete_4h_groups": len(bars),
        "incomplete_4h_groups": len(incomplete),
        "eligible_decisions": eligible,
        "unknown_decisions_initial_history": 180,
        "unknown_decisions_due_to_gaps_including_missing_cutoffs": expected_4h - 180 - eligible,
        "unknown_decisions_due_to_gaps_on_existing_4h_rows": len(bars) - 180 - eligible,
        "quarantine_detail": details,
        "missing_vendor_hour_opens": missing,
        "incomplete_4h_cutoffs": incomplete,
    }


def run(root: Path, output: Path, muse_raw: Path | None = None):
    muse, fixed, module_hashes = replica()
    hourly = load(root)
    muse_hourly, quarantine, raw_rows, archives = [], [], [], []
    for path in sorted(root.glob("*.zip")):
        raw = path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            text = archive.read(archive.namelist()[0]).decode()
        muse_hourly.extend(
            muse.bars.parse_kline_csv(
                text, vintage=path.name, ingested_at="frozen-receipt", quarantine=quarantine
            )
        )
        for fields in csv.reader(io.StringIO(text)):
            factor = 1000 if int(fields[0]) >= 10**15 else 1
            raw_rows.append(
                {
                    "archive": path.name,
                    "open_time": int(fields[0]) // factor,
                    "close_time_ms": int(fields[6]) // factor,
                    "open": float(fields[1]),
                    "high": float(fields[2]),
                    "low": float(fields[3]),
                    "close": float(fields[4]),
                    "volume": float(fields[5]),
                    "raw_row_sha256": fingerprint(fields),
                }
            )
        digest = hashlib.sha256(raw).hexdigest()
        mirror = muse_raw / path.name if muse_raw else None
        archives.append(
            {
                "file": path.name,
                "sha256": digest,
                "muse_acquired_copy_sha256": hashlib.sha256(mirror.read_bytes()).hexdigest()
                if mirror and mirror.exists()
                else None,
            }
        )
    bars = aggregate_four_hours(hourly)
    muse_bars = muse.bars.aggregate_4h(muse_hourly)
    events, eligible = candidates(bars)
    muse_events = muse.candidates.scan_crossings(muse_bars)
    accepted = {e.event_id for e in spaced_events(events)}
    muse_flags = {
        e["cutoff_ms"]: e["independent"] for e in muse.candidates.space_candidates(muse_events)
    }
    assert len(events) == len(muse_events)
    assert [b.open_time for b in hourly] == [b["open_ms"] for b in muse_hourly]
    for a, b in zip(hourly, muse_hourly):
        assert all(getattr(a, k) == b[k] for k in ("open", "high", "low", "close", "volume"))
    assert len(bars) == len(muse_bars)
    for a, b in zip(bars, muse_bars):
        assert a.open_time == b["open_ms"]
        assert all(getattr(a, k) == b[k] for k in ("open", "high", "low", "close", "volume"))
    muse_by_open = {b["open_ms"]: b for b in muse_bars}
    muse_eligible = sum(
        bool(
            muse.bars.contiguous_4h_before(
                muse_bars, b.end_time, min_bars=181, by_open=muse_by_open
            )
        )
        for b in bars
    )
    opens = [b.open_time for b in hourly]
    muse_opens = [b["open_ms"] for b in muse_hourly]
    records, traces, disagreements, corrected_disagreements = [], [], Counter(), Counter()
    labels, original_labels = {}, {}
    geometry_max_error = dict.fromkeys(("sigma", "scale", "reference_price"), 0.0)
    for event, other in zip(events, muse_events):
        assert event.data_cutoff == other["cutoff_ms"]
        assert event.direction == (1 if other["direction"] == "UP" else -1)
        assert event.decision_time == int(
            datetime.fromisoformat(other["decision_time"]).timestamp() * 1000
        )
        assert (event.event_id in accepted) == muse_flags[event.data_cutoff]
        for key, left, right in (
            ("sigma", event.scale / math.sqrt(42), other["sigma"]),
            ("scale", event.scale, other["scale_S"]),
            ("reference_price", event.reference_price, other["reference_price"]),
        ):
            geometry_max_error[key] = max(geometry_max_error[key], abs(left - right))
            assert math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
        lo, hi = (
            bisect_left(opens, event.data_cutoff + HOUR),
            bisect_left(opens, event.data_cutoff + 7 * DAY),
        )
        mlo, mhi = (
            bisect_left(muse_opens, event.data_cutoff + HOUR),
            bisect_left(muse_opens, event.data_cutoff + 7 * DAY),
        )
        canonical = label(event, hourly[lo:hi])
        original = muse.labels.label_candidate(other, muse_hourly[mlo:mhi])
        corrected = fixed.label_candidate(other, muse_hourly[mlo:mhi])
        keys = (
            "outcome",
            "barrier_time",
            "mfe",
            "mae",
            "mfe_normalized",
            "mae_normalized",
            "signed_return",
        )
        left = {k: asdict(canonical)[k] for k in keys}
        right = normalize_muse(other, original)
        repaired = normalize_muse(other, corrected)
        differences = different(left, right)
        repaired_diff = different(left, repaired)
        disagreements.update(differences)
        corrected_disagreements.update(repaired_diff)
        labels[event.event_id], original_labels[event.event_id] = canonical, original
        records.append(
            {
                "event_id": event.event_id,
                "cutoff_utc": dt(event.data_cutoff).isoformat(),
                "decision_time": event.decision_time,
                "direction": other["direction"],
                "globally_spaced": event.event_id in accepted,
                "canonical_sigma": event.scale / math.sqrt(42),
                "muse_sigma": other["sigma"],
                "canonical_reference_price": event.reference_price,
                "muse_reference_price": other["reference_price"],
                "canonical_scale_S": event.scale,
                "muse_scale_S": other["scale_S"],
                "canonical": left,
                "muse_original": right,
                "muse_orientation_only": repaired,
                "muse_original_resolution_hour_open": original["resolved_ms"],
                "discrepant_fields": differences,
                "orientation_only_discrepant_fields": repaired_diff,
            }
        )
        if "outcome" in differences:
            favorable = event.reference_price * math.exp(event.direction * 2 * event.scale)
            adverse = event.reference_price * math.exp(-event.direction * event.scale)
            touches = []
            for bar in hourly[lo:hi]:
                f = event.direction * math.log(
                    (bar.high if event.direction == 1 else bar.low) / event.reference_price
                )
                a = event.direction * math.log(
                    (bar.low if event.direction == 1 else bar.high) / event.reference_price
                )
                if f >= 2 * event.scale or a <= -event.scale:
                    touches.append(
                        {
                            "open_utc": dt(bar.open_time).isoformat(),
                            "end_utc": dt(bar.end_time).isoformat(),
                            "open": bar.open,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close,
                            "favorable_log_excursion": f,
                            "adverse_log_excursion": a,
                            "hits_favorable": f >= 2 * event.scale,
                            "hits_adverse": a <= -event.scale,
                        }
                    )
            traces.append(
                {
                    "event_id": event.event_id,
                    "cutoff_utc": dt(event.data_cutoff).isoformat(),
                    "globally_spaced": event.event_id in accepted,
                    "direction": other["direction"],
                    "reference_price": event.reference_price,
                    "scale_S": event.scale,
                    "favorable_price_barrier": favorable,
                    "adverse_price_barrier": adverse,
                    "canonical_outcome": canonical.outcome,
                    "muse_original_outcome": original["outcome"],
                    "first_touch": touches[0] if touches else None,
                    "all_touch_hours": touches,
                }
            )
    audit = {}
    canonical_legs = segment_legs(bars, events, audit=audit)
    muse_legs = muse.episodes.segment_legs(muse_bars)
    large_muse = [l for l in muse_legs if l["large"] and not l["censored"]]
    frozen = json.loads(git_file(CODEX_COMMIT, "docs/research/momentum/results/CENSUS.json"))
    frozen_muse = json.loads(git_file(MUSE_COMMIT, "artifacts/momentum/mom000_census.json"))
    original_replay = json.loads(
        json.dumps(muse.census.run_census(muse_bars, muse_hourly, quarantined_rows=quarantine))
    )
    fields = (
        "UP",
        "DOWN",
        "n_1h_bars",
        "n_4h_bars",
        "n_crossings",
        "n_spaced",
        "ex_post_legs",
        "overlap_components",
    )
    assert all(original_replay[k] == frozen_muse[k] for k in fields), {
        k: {"replayed": original_replay[k], "frozen": frozen_muse[k]}
        for k in fields
        if original_replay[k] != frozen_muse[k]
    }
    label_digest = fingerprint([asdict(labels[e.event_id]) for e in events])
    assert label_digest == frozen["labels_fingerprint"]
    assert set(corrected_disagreements) <= {"mfe", "mfe_normalized"}, dict(corrected_disagreements)
    for row in records:
        geometry = dict(row["muse_orientation_only"])
        for key in ("mfe", "mfe_normalized"):
            if geometry[key] is not None:
                geometry[key] = max(0.0, geometry[key])
        assert not different(row["canonical"], geometry)

    report = {
        "scope": "MOM-000 descriptive replication; predictive_trials=0; MOM-002 not scored",
        "codex_frozen_commit": CODEX_COMMIT,
        "muse_commit": MUSE_COMMIT,
        "muse_module_sha256": module_hashes,
        "muse_manifest_fingerprint_finding": "MANIFEST calls it normalized closes; script actually hashes first/last64 CSV characters and truncates SHA256. Full84 ZIP hashes are used here.",
        "archives": archives,
        "muse_frozen_report_reproduced": True,
        "source_taxonomy": source_taxonomy(raw_rows, hourly, bars, eligible, quarantine),
        "muse_eligible_decisions": muse_eligible,
        "all_four_hour_arrays_same_length": len(bars) == len(muse_bars),
        "candidate_crossings": len(events),
        "globally_spaced_candidates": len(accepted),
        "all_candidate_timestamps_directions_clocks_spacing_match": True,
        "candidate_float_max_absolute_difference": geometry_max_error,
        "numeric_comparison_tolerance": {"absolute": 1e-12, "relative": 1e-12},
        "original_muse_field_discrepancy_counts": dict(disagreements),
        "orientation_only_remaining_discrepancy_counts": dict(corrected_disagreements),
        "orientation_and_zero_floor_remaining_discrepancy_counts": {},
        "primary_counts": {
            name: {
                "canonical": dict(
                    Counter(
                        labels[e.event_id].outcome
                        for e in events
                        if e.event_id in accepted and e.direction == side
                    )
                ),
                "muse_original": dict(
                    Counter(
                        original_labels[e.event_id]["outcome"]
                        for e in events
                        if e.event_id in accepted and e.direction == side
                    )
                ),
            }
            for side, name in ((1, "UP"), (-1, "DOWN"))
        },
        "overlap_components_7d": len(interval_groups(events, 7 * DAY)),
        "overlap_components_14d": len(interval_groups(events, 14 * DAY)),
        "muse_closed_cutoff_components_7d": len(muse.episodes.overlap_components(muse_events)),
        "muse_closed_cutoff_components_14d": len(
            muse.episodes.overlap_components(muse_events, horizon_days=14)
        ),
        "canonical_interval": "closed [decision_time=cutoff+5m, cutoff+horizon]; touching connects",
        "muse_interval": "closed [cutoff, cutoff+horizon]; touching connects",
        "canonical_label_fingerprint": label_digest,
        "frozen_mom000_label_fingerprint_unchanged": True,
        "canonical_gate": frozen["gate"],
        "mom001": "CLOSED_NOT_SCORED",
        "muse_ex_post_summary": frozen_muse["ex_post_legs"],
        "canonical_leg_state": audit,
        "canonical_large_legs_by_direction": dict(Counter(l["direction"] for l in canonical_legs)),
        "independence_warning": "Components and spacing are counts of interval geometry, not proven independent samples or a scalar effective N.",
    }
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "RECONCILIATION.json": report,
        "CANDIDATE_DIFF.json": records,
        "DISCREPANT_BARRIER_TRACES.json": traces,
        "LEG_DIFF.json": {
            "canonical_large_completed": canonical_legs,
            "canonical_state": audit,
            "muse_all": muse_legs,
            "muse_large_front_loading": [
                muse.episodes.front_loading_for_leg(l, muse_bars) for l in large_muse
            ],
        },
    }
    for name, value in artifacts.items():
        (output / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (output / "PR49_FROZEN_CENSUS.json").write_bytes(
        git_file(CODEX_COMMIT, "docs/research/momentum/results/CENSUS.json")
    )
    (output / "PR50_FROZEN_CENSUS.json").write_bytes(
        git_file(MUSE_COMMIT, "artifacts/momentum/mom000_census.json")
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "primary_counts",
                    "overlap_components_7d",
                    "overlap_components_14d",
                    "original_muse_field_discrepancy_counts",
                    "orientation_only_remaining_discrepancy_counts",
                    "canonical_gate",
                )
            },
            indent=2,
        )
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--muse-raw", type=Path)
    args = parser.parse_args()
    run(args.root, args.output, args.muse_raw)
