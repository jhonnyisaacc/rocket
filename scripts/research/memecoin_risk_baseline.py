"""MC-003 frozen risk label and terminal-liquidity stress on a new cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path


def risk_result(session: Path) -> dict:
    source = session / "mc002-result.json"
    if not source.exists():
        raise ValueError("run the frozen five-second baseline first")
    baseline = json.loads(source.read_text())
    network_cost_per_leg = baseline["network_cost_lamports_each_leg"]
    universe = [json.loads(line) for line in (session / "universe.jsonl").read_text().splitlines()]
    for row in universe:
        if row["status"] == "QUOTED":
            row["exit_feasibility"] = "EXIT_FEASIBLE"
            row["stress_return"] = row["outcome"]["net_quote_proxy_return"]
        elif row["reason"] and row["reason"].startswith("EXIT_UNAVAILABLE:"):
            entry = row.get("entry_quote")
            if not entry:
                raise ValueError("exit failure lacks entry quote provenance")
            row["exit_feasibility"] = "EXIT_UNAVAILABLE"
            spent = entry["cash"]
            row["stress_return"] = (-spent - 2 * network_cost_per_leg) / (
                spent + network_cost_per_leg)
        else:
            row["exit_feasibility"] = "UNKNOWN"
            row["stress_return"] = None

    def summarize(split: str) -> dict:
        rows = [row for row in universe if row["split"] == split]
        ranked = sorted(rows, key=lambda row: (-row["score"], row["signature"]))
        top = ranked[:max(1, math.ceil(len(ranked) / 4))] if ranked else []

        def group_summary(group: list[dict]) -> dict:
            returns = [row["stress_return"] for row in group if row["stress_return"] is not None]
            return {
                "total_scored": len(group),
                "entry_known": len(returns),
                "exit_feasible": sum(row["exit_feasibility"] == "EXIT_FEASIBLE" for row in group),
                "exit_unavailable": sum(row["exit_feasibility"] == "EXIT_UNAVAILABLE" for row in group),
                "unknown": sum(row["exit_feasibility"] == "UNKNOWN" for row in group),
                "stress_mean": statistics.mean(returns) if returns else None,
                "stress_median": statistics.median(returns) if returns else None,
                "stress_positive": sum(value > 0 for value in returns),
            }
        return {"all": group_summary(rows), "top_quartile": group_summary(top)}

    result = {
        "schema": "rocket.memecoin.mc003-risk-result.v1",
        "source_result_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "parameters_inherited_from_mc002": {
            "feature_checkpoint_seconds": baseline["feature_checkpoint_seconds"],
            "entry_seconds": baseline["entry_seconds"],
            "exit_seconds": baseline["exit_seconds"],
            "size_lamports": baseline["size_lamports"],
            "slippage_bps_each_leg": baseline["slippage_bps_each_leg"],
            "network_cost_lamports_each_leg": baseline["network_cost_lamports_each_leg"],
        },
        "terminal_exit_failure_assumption": "zero cash recovery; charge both network legs",
        "development": summarize("development"),
        "evaluation": summarize("evaluation"),
        "conclusion": "Scenario stress, not a realized liquidation or accepted strategy.",
    }
    (session / "mc003-risk-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(risk_result(arguments.session), indent=2))
