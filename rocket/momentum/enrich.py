"""Later outcome enrichment; reads immutable forecasts, never changes their payloads."""

from __future__ import annotations

import argparse
import json
import urllib.request
from dataclasses import asdict
from pathlib import Path

from rocket.momentum.collect import ENDPOINT, clock_ms, parse_live, store_blob
from rocket.momentum.core import DAY, CandidateEvent, label
from rocket.momentum.shadow import ShadowLog


def enrich(root: Path, *, now_fn=clock_ms, fetch=None):
    now = now_fn()
    journal = ShadowLog(root / "shadow.sqlite")
    enriched, pending = 0, 0
    for identity, record in journal.forecasts():
        candidate = record.get("candidate_event")
        if candidate is None:
            continue
        event = CandidateEvent(**candidate)
        end = event.data_cutoff + 7 * DAY
        if now < end + 300_000:
            pending += 1
            continue
        # Idempotent: an enriched identity needs no new source revision/read.
        with journal.connect() as db:
            rows = db.execute(
                "SELECT payload FROM outcomes WHERE forecast_id=?", (identity,)
            ).fetchall()
        if any(json.loads(row[0])["horizon_days"] == 7 for row in rows):
            continue
        url = (
            f"{ENDPOINT}?symbol=BTCUSDT&interval=1h&limit=1000"
            f"&startTime={event.data_cutoff + 3_600_000}&endTime={end - 1}"
        )
        if fetch is None:
            req = urllib.request.Request(
                url, headers={"User-Agent": "rocket-momentum-enrichment/1"}
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = response.read()
        else:
            raw = fetch(url)
        receipt = now_fn()
        digest = store_blob(root, raw)
        outcome = asdict(label(event, parse_live(raw, receipt)))
        outcome["available_at"] = max(outcome["available_at"], receipt)
        outcome["source_fingerprint"] = digest
        journal.append_outcome(identity, outcome, receipt)
        enriched += 1
    return {"enriched": enriched, "pending": pending, "forecast_updates": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    print(json.dumps(enrich(args.root)))
