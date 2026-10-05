"""Frozen MC-005 early net-flow rank on a new prospective cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

from rocket.research.memecoin_dataset import SCHEMA as SNAPSHOT_SCHEMA

NETWORK_SCENARIOS = (155_000, 1_000_000)


def score_snapshot(snapshot: dict) -> int:
    if snapshot["schema"] != SNAPSHOT_SCHEMA:
        raise ValueError("snapshot schema differs from frozen MC-005 input")
    features = snapshot["features"]
    buys, sells = features["observed_buys_5s"], features["observed_sells_5s"]
    if not all(isinstance(value, int) and value >= 0 for value in (buys, sells)):
        raise ValueError("early trade counts must be nonnegative integers")
    return buys - sells


def scenario_return(row: dict, fee: int) -> float | None:
    if row["status"] == "QUOTED":
        entry = row["outcome"]["entry_quote"]["cash"]
        exit_cash = row["outcome"]["stressed_exit_cash_lamports"]
    elif (row.get("reason") or "").startswith("EXIT_UNAVAILABLE:"):
        entry = row["entry_quote"]["cash"]
        exit_cash = 0
    else:
        return None
    return (exit_cash - entry - 2 * fee) / (entry + fee)


def summarize(group: list[dict], fee: int) -> dict:
    known = [row for row in group if row["returns"][str(fee)] is not None]
    values = [row["returns"][str(fee)] for row in known]
    unavailable = sum(row["exit_feasibility"] == "EXIT_UNAVAILABLE" for row in known)
    quoted_values = [row["returns"][str(fee)] for row in known
                     if row["exit_feasibility"] == "EXIT_FEASIBLE"]
    return {"scored": len(group), "entry_known": len(known),
            "exit_feasible": len(quoted_values), "exit_unavailable": unavailable,
            "unknown": len(group) - len(known),
            "exit_unavailable_rate": unavailable / len(known) if known else None,
            "stress_mean": statistics.mean(values) if values else None,
            "stress_median": statistics.median(values) if values else None,
            "quoted_mean": statistics.mean(quoted_values) if quoted_values else None,
            "quoted_n": len(quoted_values),
            "stress_positive": sum(value > 0 for value in values)}


def evaluate(session: Path) -> dict:
    audit = json.loads((session / "audit.json").read_text())
    if audit["coverage_status"] != "SIGNATURES_MATCH_INNER_SLOTS" or audit["event_decode_error_count"]:
        raise ValueError("covered, strictly decoded inner slots required")
    if audit["created_mint_trade_state_continuity"]["native_nonmayhem_fail"] or audit[
        "native_nonmayhem_quote_validation"]["fail"]:
        raise ValueError("protocol continuity or quote validation failed")
    source = session / "mc002-result.json"
    baseline = json.loads(source.read_text())
    if (baseline["feature_checkpoint_seconds"], baseline["entry_seconds"],
        baseline["exit_seconds"], baseline["size_lamports"],
        baseline["slippage_bps_each_leg"], baseline["network_cost_lamports_each_leg"]) != (
            5, 7, 67, 10_000_000, 200, 155_000):
        raise ValueError("base quote policy differs from frozen MC-005 policy")
    snapshots = {row["identity"].split(":")[-1]: row for line in (
        session / "snapshots.jsonl").read_text().splitlines() if (row := json.loads(line))}
    universe = [json.loads(line) for line in (session / "universe.jsonl").read_text().splitlines()]
    scored = []
    for row in universe:
        if row["score"] is None:
            continue
        snapshot = snapshots.get(row["mint"])
        if snapshot is None or snapshot["fingerprint"] != row["snapshot_fingerprint"]:
            raise ValueError("missing or mismatched point-in-time snapshot")
        score = score_snapshot(snapshot)
        if row["status"] == "QUOTED":
            exit_feasibility = "EXIT_FEASIBLE"
        elif (row.get("reason") or "").startswith("EXIT_UNAVAILABLE:"):
            exit_feasibility = "EXIT_UNAVAILABLE"
        else:
            exit_feasibility = "UNKNOWN"
        scored.append({"mint": row["mint"], "signature": row["signature"],
                       "split": row["split"], "flow_score": score,
                       "snapshot_fingerprint": snapshot["fingerprint"],
                       "exit_feasibility": exit_feasibility,
                       "returns": {str(fee): scenario_return(row, fee)
                                   for fee in NETWORK_SCENARIOS}})

    splits = {}
    for split in ("development", "evaluation"):
        rows = [row for row in scored if row["split"] == split]
        ranked = sorted(rows, key=lambda row: (-row["flow_score"], row["signature"]))
        top = ranked[:math.ceil(len(ranked) / 4)]
        scenarios = {str(fee): {"all": summarize(rows, fee),
                                "top_quartile": summarize(top, fee)}
                     for fee in NETWORK_SCENARIOS}
        splits[split] = {"scored": len(rows), "top_quartile_size": len(top),
                         "score_ties": len({row["flow_score"] for row in rows}) < len(rows),
                         "scenarios": scenarios}
    evaluation = splits["evaluation"]["scenarios"]
    reference = evaluation[str(NETWORK_SCENARIOS[0])]
    all_risk = reference["all"]["exit_unavailable_rate"]
    top_risk = reference["top_quartile"]["exit_unavailable_rate"]
    enough = reference["all"]["entry_known"] >= 30
    risk_better = top_risk is not None and all_risk is not None and top_risk < all_risk
    economics = all(
        (scenario["top_quartile"]["stress_mean"] is not None
         and scenario["all"]["stress_mean"] is not None
         and scenario["top_quartile"]["stress_mean"] > 0
         and scenario["top_quartile"]["stress_mean"] > scenario["all"]["stress_mean"])
        for scenario in evaluation.values())
    result = {"schema": "rocket.memecoin.mc005-flow-result.v1",
              "audit_sha256": hashlib.sha256((session / "audit.json").read_bytes()).hexdigest(),
              "source_result_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "score": "observed_buys_5s - observed_sells_5s",
              "network_fee_scenarios_lamports_per_leg": NETWORK_SCENARIOS,
              "universe_count": len(universe), "scored_count": len(scored),
              "development": splits["development"], "evaluation": splits["evaluation"],
              "minimum_promotion_gates": {"evaluation_entry_known_at_least_30": enough,
                                          "top_exit_risk_lower": risk_better,
                                          "top_positive_and_better_stress_both_fees": economics},
              "minimum_promotion_gates_pass": enough and risk_better and economics,
              "conclusion_scope": "Minimum gates only; actual inclusion and route execution remain unmeasured."}
    (session / "mc005-flow-rows.jsonl").write_text("".join(
        json.dumps(row, sort_keys=True) + "\n" for row in scored))
    (session / "mc005-flow-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.session), indent=2))
