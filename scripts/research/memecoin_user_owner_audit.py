"""Check emitted Pump trade user against token-account owner in MC-004 sample."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event_sized_account_owner(meta: dict, mint: str, expected_delta: int) -> str | None:
    before = {row["accountIndex"]: row for row in meta.get("preTokenBalances") or []
              if row["mint"] == mint}
    after = {row["accountIndex"]: row for row in meta.get("postTokenBalances") or []
             if row["mint"] == mint}
    matches = []
    for index in before.keys() | after.keys():
        start = int(before.get(index, {"uiTokenAmount": {"amount": "0"}})["uiTokenAmount"]["amount"])
        end = int(after.get(index, {"uiTokenAmount": {"amount": "0"}})["uiTokenAmount"]["amount"])
        if end - start == expected_delta:
            owner = (after if expected_delta > 0 else before).get(index, {}).get("owner")
            matches.append(owner)
    return matches[0] if len(matches) == 1 else None


def audit(session: Path, sample: Path) -> dict:
    source = session / "observations.jsonl"
    selection_path = sample / "selection.json"
    observations: dict[str, list[dict]] = {}
    for line in source.read_text().splitlines():
        row = json.loads(line)
        if row["event_type"] == "TradeEvent":
            observations.setdefault(row["signature"], []).append(row)
    selection = json.loads(selection_path.read_text())
    rows = []
    for chosen in selection["selected"]:
        if chosen["stratum"] == "multi_trade":
            continue
        signature = chosen["signature"]
        events = observations.get(signature, [])
        response_path = sample / "responses" / f"{signature}.json"
        record = json.loads(response_path.read_text())
        response = next((item["body"]["result"] for item in reversed(record["attempts"])
                         if item.get("body", {}).get("result")), None)
        if len(events) != 1 or response is None:
            status = "UNAVAILABLE_OR_MULTI_EVENT"
            owner = user = None
        else:
            event = events[0]
            user = event.get("user")
            delta = event["token_amount"] * (1 if event["is_buy"] else -1)
            owner = event_sized_account_owner(response["meta"], event["mint"], delta)
            status = "MATCH" if user and owner == user else (
                "MISMATCH" if user and owner else "AMBIGUOUS")
        rows.append({"signature": signature, "stratum": chosen["stratum"],
                     "status": status, "event_user": user, "event_sized_token_account_owner": owner,
                     "transaction_response_sha256": digest(response_path)})
    result = {"schema": "rocket.memecoin.mc004-user-owner-audit.v1",
              "observations_sha256": digest(source), "selection_sha256": digest(selection_path),
              "counts": dict(Counter(row["status"] for row in rows)), "rows": rows,
              "interpretation": "Event user can be a routed intermediary; account owner is not automatically beneficial owner."}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("sample", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.session, args.sample)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["counts"]))
