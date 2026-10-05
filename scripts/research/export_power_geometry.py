"""Export causal candidate geometry only, from already-present frozen spot ZIPs.

Never import label/census/reconciliation code, read outcome artifacts or acquire data.
This separate exporter is not part of the synthetic simulation's input surface.
"""

import argparse
import ast
import calendar
import csv
import hashlib
import io
import json
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

REVISION = "7c42582168e7538cfac00393bc3ffce54beb21b1"
ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "research/governance/power/population.geometry.json"


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{REVISION}:{path}"])


def causal_core():
    """Execute only definitions preceding ForwardLabel; no forward code exists in namespace."""
    import sys

    raw = blob("rocket/momentum/core.py")
    tree = ast.parse(raw)
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ForwardLabel":
            break
        nodes.append(node)
    module = ModuleType("rocket_power_causal_core")
    sys.modules[module.__name__] = module
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "pinned-causal-core", "exec"), module.__dict__)  # noqa: S102 -- exact SHA-pinned, outcome definitions removed
    assert "label" not in module.__dict__ and "ForwardLabel" not in module.__dict__
    return module, hashlib.sha256(raw).hexdigest()


def export(raw_root):
    core, core_hash = causal_core()
    source = blob("rocket/momentum/source.py")
    parser = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "parse_archive")
    namespace = {"calendar": calendar, "csv": csv, "io": io, "zipfile": zipfile,
                 "UTC": UTC, "datetime": datetime, "HOUR": core.HOUR, "LAG": core.LAG,
                 "Bar": core.Bar, "fingerprint": core.fingerprint}
    exec(compile(ast.Module(body=[parser], type_ignores=[]), "pinned-archive-parser", "exec"), namespace)  # noqa: S102 -- only the pinned pure parser, no acquisition code
    frozen = json.loads(blob("docs/research/momentum/SOURCE_MANIFEST.json"))
    hashes = {entry["file"]: entry["sha256"] for entry in frozen["files"]}
    bars, files = [], []
    for year in range(2019, 2026):
        for month in range(1, 13):
            name = f"BTCUSDT-1h-{year}-{month:02d}.zip"
            path = raw_root / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Existing regular ZIP required; acquisition is disabled")
            raw = path.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            if hashes.get(name) != sha:
                raise ValueError("Spot bytes differ from frozen MOM-000 source")
            receipt = json.loads((raw_root / (name + ".receipt.json")).read_text())
            parsed = namespace["parse_archive"](raw, year, month, receipt["ingested_at"])
            bars.extend(parsed)
            files.append({"file": name, "sha256": sha})
    events, _ = core.candidates(core.aggregate_four_hours(bars))
    spaced = {e.event_id for e in core.spaced_events(events)}
    groups = {days: {identity: group for group, members in enumerate(core.interval_groups(events, days * core.DAY))
                     for identity in members} for days in (7, 14)}
    times = {b.open_time for b in bars}
    rows = []
    for e in events:
        year = core.dt(e.decision_time).year
        rows.append({"id": e.event_id, "decision_time": e.decision_time,
                     "cutoff": e.data_cutoff, "direction": e.direction, "scale": e.scale,
                     "year": year, "fold": year if year in (2023, 2024, 2025) else None,
                     "component_7d": groups[7][e.event_id], "component_14d": groups[14][e.event_id],
                     "spaced": e.event_id in spaced,
                     "horizon_supported": all(e.data_cutoff + h * core.HOUR in times for h in range(1, 168))})
    counts = [len(rows), len(spaced), len(set(groups[7].values())), len(set(groups[14].values()))]
    if counts != [354, 107, 128, 47] or sum(e.direction == 1 for e in events) != 219:
        raise ValueError("Frozen candidate geometry does not reconcile")
    value = {"schema": "rocket.power.geometry.v1", "provenance": {
        "source_revision": REVISION, "causal_core_sha256": core_hash,
        "source_parser_sha256": hashlib.sha256(source).hexdigest(), "source_files": files,
        "real_outcomes_accessed": False, "feature_completeness": "UNVERIFIED",
        "coverage_assumption_start": "2020-09-01T00:00:00Z",
        "generator": core.CONTRACT, "intervals": "[cutoff+5m, cutoff+horizon]"}, "rows": rows}
    DESTINATION.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"geometry": str(DESTINATION), "counts": counts,
                      "sha256": hashlib.sha256(DESTINATION.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    export(parser.parse_args().raw_root)
