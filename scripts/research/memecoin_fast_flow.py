"""MC-010 frozen net-flow rank restricted to fast, transaction-verified creates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime
from pathlib import Path

from scripts.research.memecoin_flow_baseline import NETWORK_SCENARIOS, summarize
from scripts.research.memecoin_flow_diagnostics import (
    exact_binomial_interval,
    fisher_lower_tail,
    percentile,
)


def group_summary(rows: list[dict], fee: int) -> dict:
    base = summarize(rows, fee)
    known = base["entry_known"]
    base["exit_unavailable_exact_95_interval"] = exact_binomial_interval(
        base["exit_unavailable"], known)
    return base


def leave_best_out(rows: list[dict], fee: int) -> float | None:
    values = [row["returns"][str(fee)] for row in rows
              if row["returns"][str(fee)] is not None]
    return statistics.mean(sorted(values)[:-1]) if len(values) > 1 else None


def evaluate(session: Path, identities_path: Path) -> dict:
    audit_path = session / "audit.json"
    audit = json.loads(audit_path.read_text())
    if audit["coverage_status"] != "SIGNATURES_MATCH_INNER_SLOTS" or not audit.get(
            "signature_quarantine_policy"):
        raise ValueError("MC-010 requires independently covered valid signatures and raw quarantine")
    if (audit["successful_transactions_with_truncated_logs"]
            or audit["event_decode_error_count"] or audit["event_transaction_identity_mismatches"]
            or audit["created_mint_trade_state_continuity"]["native_nonmayhem_fail"]
            or audit["native_nonmayhem_quote_validation"]["fail"]):
        raise ValueError("MC-010 protocol or collector gate failed")
    flow = json.loads((session / "mc005-flow-result.json").read_text())
    if flow["score"] != "observed_buys_5s - observed_sells_5s":
        raise ValueError("flow score differs from frozen design")
    identities = json.loads(identities_path.read_text())
    create_rows = {row["signature"]: row for line in
                   (session / "observations.jsonl").read_text().splitlines()
                   if (row := json.loads(line))["event_type"] == "CreateEvent"}
    all_lags = [(datetime.fromisoformat(row["available_at"]) -
                 datetime.fromisoformat(row["event_time"])).total_seconds()
                for row in create_rows.values()]
    scored = [json.loads(line) for line in
              (session / "mc005-flow-rows.jsonl").read_text().splitlines()]
    fast = []
    unresolved = []
    for row in scored:
        created = create_rows[row["signature"]]
        lag = (datetime.fromisoformat(created["available_at"]) -
               datetime.fromisoformat(created["event_time"])).total_seconds()
        if lag > 5:
            continue
        identity = identities["rows"].get(row["signature"])
        if identity is None or identity["status"] not in ("CAPTURED_STRICT", "RECHECKED_STRICT"):
            unresolved.append({"signature": row["signature"], "mint": row["mint"],
                               "status": identity["status"] if identity else "NOT_CHECKED"})
            continue
        fast.append({**row, "create_received_at": created["available_at"],
                     "create_event_timestamp_to_receipt_seconds": lag,
                     "original_all_scored_split": row["split"],
                     "identity_status": identity["status"]})
    fast.sort(key=lambda row: (row["create_received_at"], row["signature"]))
    boundary = math.ceil(0.7 * len(fast))
    for index, row in enumerate(fast):
        row["split"] = "development" if index < boundary else "evaluation"
    splits = {}
    for name in ("development", "evaluation"):
        rows = [row for row in fast if row["split"] == name]
        ranked = sorted(rows, key=lambda row: (-row["flow_score"], row["signature"]))
        top = ranked[:math.ceil(len(rows) / 4)]
        rest = ranked[len(top):]
        scenarios = {}
        for fee in NETWORK_SCENARIOS:
            all_stats = group_summary(rows, fee)
            top_stats = group_summary(top, fee)
            rest_stats = group_summary(rest, fee)
            scenarios[str(fee)] = {
                "all": all_stats, "top_quartile": top_stats, "rest": rest_stats,
                "top_leave_best_out_stress_mean": leave_best_out(top, fee),
                "risk_difference_top_minus_rest": (
                    top_stats["exit_unavailable_rate"] - rest_stats["exit_unavailable_rate"]
                    if top_stats["exit_unavailable_rate"] is not None
                    and rest_stats["exit_unavailable_rate"] is not None else None),
                "one_sided_fisher_p_descriptive": fisher_lower_tail(
                    top_stats["exit_unavailable"], top_stats["entry_known"],
                    rest_stats["exit_unavailable"], rest_stats["entry_known"]),
            }
        splits[name] = {"scored": len(rows), "top_quartile_size": len(top),
                        "score_ties": len({row["flow_score"] for row in rows}) < len(rows),
                        "scenarios": scenarios}
    eval_ref = splits["evaluation"]["scenarios"]["155000"]
    enough = eval_ref["all"]["entry_known"] >= 30 and eval_ref["top_quartile"][
        "entry_known"] >= 10
    risk = all(
        split["scenarios"]["155000"]["risk_difference_top_minus_rest"] is not None
        and split["scenarios"]["155000"]["risk_difference_top_minus_rest"] < 0
        for split in splits.values())
    economic = all(
        scenario["top_quartile"]["stress_mean"] is not None
        and scenario["all"]["stress_mean"] is not None
        and scenario["top_quartile"]["stress_mean"] > 0
        and scenario["top_quartile"]["stress_mean"] > scenario["all"]["stress_mean"]
        for split in splits.values() for scenario in split["scenarios"].values())
    leaveout = all(
        scenario["top_leave_best_out_stress_mean"] is not None
        and scenario["top_leave_best_out_stress_mean"] > 0
        for scenario in splits["evaluation"]["scenarios"].values())
    (session / "mc010-fast-flow-rows.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in fast))
    result = {"schema": "rocket.memecoin.mc010-fast-flow.v1",
              "audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
              "flow_result_sha256": hashlib.sha256((session / "mc005-flow-result.json").read_bytes()).hexdigest(),
              "identity_result_sha256": hashlib.sha256(identities_path.read_bytes()).hexdigest(),
              "all_decoded_create_count": len(create_rows),
              "all_create_receipt_age_seconds": {
                  "n": len(all_lags), "median": statistics.median(all_lags) if all_lags else None,
                  "p90": percentile(all_lags, 0.9),
                  "above_5_seconds": sum(value > 5 for value in all_lags),
                  "above_10_seconds": sum(value > 10 for value in all_lags)},
              "all_scored_count": len(scored),
              "fast_scored_before_identity_count": len(fast) + len(unresolved),
              "fast_identity_unresolved_count": len(unresolved),
              "fast_identity_unresolved_sample": unresolved[:20],
              "fast_identity_verified_count": len(fast),
              "development": splits["development"], "evaluation": splits["evaluation"],
              "minimum_candidate_gates": {
                  "collector_error_free": not audit["capture_errors"],
                  "evaluation_sample_minimum": enough,
                  "top_exit_risk_lower_in_both_splits": risk,
                  "top_positive_and_better_stress_both_splits_both_fees": economic,
                  "evaluation_top_positive_after_best_removed_both_fees": leaveout},
              "minimum_candidate_gates_pass": not audit["capture_errors"]
              and enough and risk and economic and leaveout,
              "conclusion_scope": "Modeled static-state quotes and zero-recovery stress only; no achieved fills."}
    (session / "mc010-fast-flow-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--identities", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.session, args.identities), indent=2))
