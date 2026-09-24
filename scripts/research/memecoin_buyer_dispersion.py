"""MC-015 frozen signed early-buyer size dispersion and costed comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

FEES = (155_000, 1_000_000)
STRICT = {"CAPTURED_STRICT", "RECHECKED_STRICT"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dispersion(buys: list[dict]) -> float:
    spend: dict[str, int] = defaultdict(int)
    for buy in buys:
        owner = buy["token_account_owner"]
        amount = buy["event_sol_amount"]
        if not isinstance(owner, str) or not owner or not isinstance(amount, int) or amount <= 0:
            raise ValueError("buyer owner and positive integer Pump SOL amount required")
        spend[owner] += amount
    k = len(spend)
    if k == 0:
        raise ValueError("at least one signed buyer required")
    if k == 1:
        return 0.0
    total = sum(spend.values())
    squared = total * total
    return (squared - sum(amount * amount for amount in spend.values())) * k / (
        squared * (k - 1))


def summarize(group: list[dict], fee: int) -> dict:
    values = [row["direct_returns"][str(fee)] for row in group
              if row["direct_returns"][str(fee)] is not None]
    quoted = [row["direct_returns"][str(fee)] for row in group
              if row["direct_quote_status"] == "QUOTED"]
    unavailable = sum(row["direct_quote_status"] == "EXIT_UNAVAILABLE" for row in group)
    return {"scored": len(group), "known_entry": len(values), "quoted": len(quoted),
            "exit_unavailable": unavailable, "unknown_or_no_entry": len(group) - len(values),
            "exit_unavailable_rate": unavailable / len(values) if values else None,
            "stress_mean": statistics.mean(values) if values else None,
            "stress_median": statistics.median(values) if values else None,
            "stress_positive": sum(value > 0 for value in values),
            "quoted_mean": statistics.mean(quoted) if quoted else None,
            "quoted_n": len(quoted),
            "leave_best_out_stress_mean": (statistics.mean(sorted(values)[:-1])
                                           if len(values) >= 2 else None)}


def evaluate(session: Path, account_result: Path, actor_result: Path) -> dict:
    direct = json.loads(account_result.read_text())
    actor = json.loads(actor_result.read_text())
    if not direct["data_gate_pass"] or not actor["data_gate_pass"]:
        raise ValueError("covered direct account and signed actor inputs required")
    universe = [json.loads(line) for line in (session / "universe.jsonl").read_text().splitlines()]
    universe_by_signature = {row["signature"]: row for row in universe}
    direct_rows = {row["signature"]: row for row in direct["rows"]}
    actor_by_create: dict[str, list[dict]] = defaultdict(list)
    for buy in actor["rows"]:
        actor_by_create[buy["create_signature"]].append(buy)
    if not set(universe_by_signature) <= set(direct_rows):
        raise ValueError("direct-account result misses baseline universe creates")
    rows = []
    for source in universe:
        signature = source["signature"]
        direct_row = direct_rows[signature]
        buys = actor_by_create.get(signature, [])
        row = {"signature": signature, "mint": source["mint"],
               "split": source["split"], "baseline_status": source["status"],
               "identity_status": direct_row["identity_status"],
               "flow_score": direct_row.get("flow_score"),
               "direct_quote_status": direct_row["direct_quote_status"],
               "direct_returns": direct_row["direct_returns"],
               "direct_minus_event_state": direct_row.get("direct_minus_event_state"),
               "selected_buy_count": len(buys),
               "score": None, "score_status": "UNKNOWN"}
        if source["score"] is None:
            row["score_status"] = "BASELINE_EXCLUDED"
        elif direct_row["identity_status"] not in STRICT:
            row["score_status"] = "CREATE_IDENTITY_UNVERIFIED"
        elif not buys:
            row["score_status"] = "NO_EARLY_SIGNED_BUY"
        elif not all(buy["owner_available_by_checkpoint"] for buy in buys):
            row["score_status"] = "BUY_OWNER_UNAVAILABLE_BY_CHECKPOINT"
        elif any(not isinstance(buy.get("event_sol_amount"), int)
                 or buy["event_sol_amount"] <= 0 for buy in buys):
            row["score_status"] = "BUY_SIZE_UNAVAILABLE"
        else:
            row["score"] = dispersion(buys)
            row["score_status"] = "SCORED"
            row["unique_signed_owners"] = len({buy["token_account_owner"] for buy in buys})
            row["selected_buy_sol_lamports"] = sum(buy["event_sol_amount"] for buy in buys)
            row["buyer_event_signatures"] = [buy["signature"] for buy in buys]
        rows.append(row)
    score_known = [row for row in rows if row["score"] is not None]
    splits = {}
    for split in ("development", "evaluation"):
        group = [row for row in score_known if row["split"] == split]
        by_dispersion = sorted(group, key=lambda row: (-row["score"], row["signature"]))
        by_flow = sorted(group, key=lambda row: (-row["flow_score"], row["signature"]))
        top_n = math.ceil(len(group) / 4)
        dispersion_top = by_dispersion[:top_n]
        flow_top = by_flow[:top_n]
        rest = by_dispersion[top_n:]
        splits[split] = {"score_known": len(group), "top_quartile_size": top_n,
                         "score_ties": len({row["score"] for row in group}) < len(group),
                         "owner_count_distribution": dict(Counter(
                             row["unique_signed_owners"] for row in group)),
                         "fees": {str(fee): {
                             "all": summarize(group, fee),
                             "dispersion_top": summarize(dispersion_top, fee),
                             "dispersion_rest": summarize(rest, fee),
                             "flow_top_same_subset": summarize(flow_top, fee)}
                             for fee in FEES}}
    evaluation = splits["evaluation"]["fees"]
    gates = {"evaluation_known_entries_at_least_30": evaluation[str(FEES[0])]["all"][
        "known_entry"] >= 30,
        "evaluation_top_known_entries_at_least_8": evaluation[str(FEES[0])][
            "dispersion_top"]["known_entry"] >= 8,
        "positive_top_stress_both_splits_both_fees": all(
            (mean := splits[split]["fees"][str(fee)]["dispersion_top"]["stress_mean"])
            is not None and mean > 0 for split in ("development", "evaluation")
            for fee in FEES),
        "positive_eval_leave_best_out_both_fees": all(
            (mean := evaluation[str(fee)]["dispersion_top"]["leave_best_out_stress_mean"])
            is not None and mean > 0 for fee in FEES),
        "eval_top_beats_flow_top_same_subset_both_fees": all(
            (new := evaluation[str(fee)]["dispersion_top"]["stress_mean"]) is not None
            and (old := evaluation[str(fee)]["flow_top_same_subset"]["stress_mean"])
            is not None and new > old for fee in FEES)}
    paired = [row["direct_minus_event_state"][str(FEES[0])] for row in score_known
              if row["direct_minus_event_state"] and row["direct_minus_event_state"][
                  str(FEES[0])] is not None]
    eligible_count = sum(row["score"] is not None for row in universe)
    return {"schema": "rocket.memecoin.mc015-buyer-dispersion.v1",
            "direct_result_sha256": digest(account_result),
            "actor_result_sha256": digest(actor_result),
            "universe_sha256": digest(session / "universe.jsonl"),
            "universe_count": len(rows), "baseline_eligible_count": eligible_count,
            "score_status_counts": dict(Counter(row["score_status"] for row in rows)),
            "score_known_count": len(score_known),
            "score_known_fraction_of_baseline_eligible": (
                len(score_known) / eligible_count if eligible_count else None),
            "development": splits["development"], "evaluation": splits["evaluation"],
            "paired_direct_event_state_count": len(paired),
            "paired_direct_event_state_exact": sum(value == 0 for value in paired),
            "promotion_gates": gates, "minimum_economic_candidate_gate_pass": all(gates.values()),
            "rows": rows,
            "scope": "Frozen curve-account quote/stress comparison; no achieved fills, alternate route or beneficial-controller proof."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("account_result", type=Path)
    parser.add_argument("actor_result", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.session, args.account_result, args.actor_result)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
