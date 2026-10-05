from __future__ import annotations

import json
from datetime import UTC, datetime

from scripts.research.memecoin_alternate_pool_probe import report, select


def test_later_pair_creation_cannot_be_original_exit(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    universe = [
        {"mint": "unavailable", "status": "CENSORED",
         "reason": "EXIT_UNAVAILABLE:insufficient exit liquidity",
         "created_available_at": "2026-09-24T00:00:00+00:00"},
        {"mint": "quoted", "status": "QUOTED", "reason": None,
         "created_available_at": "2026-09-24T00:00:00+00:00"},
    ]
    (session / "universe.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in universe))
    selection_path = tmp_path / "selection.json"
    selected = select(session)
    selection_path.write_text(json.dumps(selected) + "\n")
    responses = tmp_path / "responses"
    responses.mkdir()
    later_ms = int(datetime(2026, 9, 24, 0, 2, tzinfo=UTC).timestamp() * 1000)
    earlier_ms = int(datetime(2026, 9, 24, 0, 1, tzinfo=UTC).timestamp() * 1000)
    pair = lambda mint, created: {"chainId": "solana", "dexId": "other",
                                  "pairAddress": f"pool-{mint}",
                                  "baseToken": {"address": mint},
                                  "quoteToken": {"address": "sol"},
                                  "pairCreatedAt": created}
    (responses / "batch-000.json").write_text(json.dumps({
        "requested_mints": [row["mint"] for row in selected["selected"]],
        "attempts": [{"http_status": 200,
                      "body": [pair("unavailable", later_ms), pair("quoted", earlier_ms)]}],
    }))
    result = report(session, selection_path, responses)
    assert result["groups"]["curve_unavailable"]["other_venue_timestamp_candidate"] == 0
    assert result["groups"]["quoted_control"]["other_venue_timestamp_candidate"] == 1
    assert result["rows"][0]["pairs"][0]["creation_time_screen"] == "AFTER_EXIT"
