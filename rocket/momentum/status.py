"""Audit immutable forecast/source integrity and expected scheduled coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rocket.momentum.collect import clock_ms
from rocket.momentum.core import FOUR_HOURS, LAG
from rocket.momentum.shadow import ShadowLog


def status(root: Path, now: int | None = None):
    now = clock_ms() if now is None else now
    journal = ShadowLog(root / "shadow.sqlite")
    records = journal.forecasts()
    blobs = set()
    for _, record in records:
        for digest in record["source_fingerprints"].values():
            if digest is None:
                continue
            path = root / "sources" / f"{digest}.json"
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("source blob missing or integrity mismatch")
            blobs.add(digest)
    first_cutoff = min((r["data_cutoff"] for _, r in records), default=None)
    scheduled = {r["data_cutoff"] for _, r in records if r["collection_mode"] == "scheduled"}
    expected = (
        list(range(first_cutoff + FOUR_HOURS, now // FOUR_HOURS * FOUR_HOURS + 1, FOUR_HOURS))
        if first_cutoff is not None
        else []
    )
    expected = [t for t in expected if t + LAG <= now]
    with journal.connect() as db:
        rows = db.execute("SELECT payload,sha256 FROM outcomes").fetchall()
    from rocket.momentum.core import fingerprint

    for raw, digest in rows:
        if fingerprint(json.loads(raw)) != digest:
            raise ValueError("outcome integrity mismatch")
    return {
        "audited_at": now,
        "forecast_records": len(records),
        "outcome_records": len(rows),
        "source_blobs_verified": len(blobs),
        "forecast_ids": [i for i, _ in records],
        "first_decision_time": min((r["decision_time"] for _, r in records), default=None),
        "latest_decision_time": max((r["decision_time"] for _, r in records), default=None),
        "scheduled_slots_expected_since_startup": len(expected),
        "scheduled_slots_recorded": len(scheduled),
        "missing_scheduled_cutoffs": [t for t in expected if t not in scheduled],
        "source_states": [r["source_status"] for _, r in records],
        "model_versions": sorted({r["model_version"] for _, r in records}),
        "integrity": "VERIFIED",
        "automation_id": "btc-momentum-prospective-shadow",
        "automation_state": "CONFIGURED_ACTIVE_NOT_YET_SUSTAINED_VALIDATION",
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
