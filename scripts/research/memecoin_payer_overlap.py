"""MC-016 deterministic point-in-time fee-payer overlap diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(session: Path, actor_path: Path) -> dict:
    actor = json.loads(actor_path.read_text())
    if not actor["data_gate_pass"] or actor["audit_sha256"] != digest(session / "audit.json"):
        raise ValueError("covered actor result must match this primary audit")
    rows = actor["rows"]
    if len(rows) != actor["selected_core_buys"]:
        raise ValueError("selected buy denominator differs from actor rows")
    if len({(row["create_signature"], row["signature"]) for row in rows}) != len(rows):
        raise ValueError("duplicate selected buy")

    by_create: dict[str, list[dict]] = defaultdict(list)
    timely = []
    for row in rows:
        by_create[row["create_signature"]].append(row)
        if not row["owner_available_by_checkpoint"]:
            continue
        if row["status"] != "OWNER_IDENTIFIED" or not all(
                key in row for key in ("token_account_owner", "fee_payer",
                                        "fee_payer_matches_owner", "owner_is_signer")):
            raise ValueError("timely owner missing signed transaction fields")
        if not row["token_account_owner"] or not row["fee_payer"]:
            raise ValueError("timely owner or payer is empty")
        timely.append(row)
    if len(timely) != actor["verified_owner_by_checkpoint"]:
        raise ValueError("timely denominator differs from actor report")

    payer_creates: dict[str, set[str]] = defaultdict(set)
    create_rows = []
    multi_owner = shared_payer = complete_multi_owner = 0
    for create_signature, selected in sorted(by_create.items()):
        known = [row for row in selected if row["owner_available_by_checkpoint"]]
        owners = {row["token_account_owner"] for row in known}
        payers: dict[str, set[str]] = defaultdict(set)
        for row in known:
            payers[row["fee_payer"]].add(row["token_account_owner"])
            payer_creates[row["fee_payer"]].add(create_signature)
        eligible = len(known) >= 2 and len(owners) >= 2
        shared = any(len(payer_owners) >= 2 for payer_owners in payers.values())
        if eligible:
            multi_owner += 1
            complete_multi_owner += len(known) == len(selected)
            shared_payer += shared
        create_rows.append({"create_signature": create_signature,
                            "selected_buys": len(selected), "timely_buys": len(known),
                            "distinct_timely_owners": len(owners),
                            "distinct_timely_payers": len(payers),
                            "multi_owner_eligible": eligible,
                            "different_owners_shared_payer": shared})

    return {"schema": "rocket.memecoin.mc016-payer-overlap.v1",
            "audit_sha256": digest(session / "audit.json"),
            "actor_result_sha256": digest(actor_path),
            "selected_core_buys": len(rows),
            "timely_usable_buys": len(timely),
            "unknown_or_late_buys": len(rows) - len(timely),
            "creates_with_selected_buys": len(by_create),
            "multi_owner_eligible_creates": multi_owner,
            "complete_multi_owner_eligible_creates": complete_multi_owner,
            "different_owners_shared_payer_creates": shared_payer,
            "timely_owner_equals_fee_payer_buys": sum(
                row["fee_payer_matches_owner"] for row in timely),
            "timely_owner_is_signer_buys": sum(row["owner_is_signer"] for row in timely),
            "distinct_timely_payers": len(payer_creates),
            "payers_seen_across_multiple_creates": sum(
                len(creates) >= 2 for creates in payer_creates.values()),
            "rows": create_rows,
            "scope": "Shared transaction payer is observable; funding and beneficial control are not inferred."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("actor_result", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.session, args.actor_result)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
