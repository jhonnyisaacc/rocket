"""MC-006 frozen latency, participant-address and exit-risk diagnostics."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

NATIVE_QUOTE = "11111111111111111111111111111111"


def binomial_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p)**(n - i) for i in range(k + 1))


def exact_binomial_interval(bad: int, total: int, alpha: float = 0.05) -> list[float] | None:
    if total == 0:
        return None
    if not 0 <= bad <= total:
        raise ValueError("invalid binomial count")
    low = 0.0
    if bad:
        left, right = 0.0, 1.0
        for _ in range(60):
            middle = (left + right) / 2
            tail = 1 - binomial_cdf(bad - 1, total, middle)
            if tail < alpha / 2:
                left = middle
            else:
                right = middle
        low = (left + right) / 2
    high = 1.0
    if bad < total:
        left, right = 0.0, 1.0
        for _ in range(60):
            middle = (left + right) / 2
            tail = binomial_cdf(bad, total, middle)
            if tail > alpha / 2:
                left = middle
            else:
                right = middle
        high = (left + right) / 2
    return [low, high]


def fisher_lower_tail(top_bad: int, top_total: int, rest_bad: int, rest_total: int) -> float | None:
    if not top_total or not rest_total:
        return None
    all_bad, all_total = top_bad + rest_bad, top_total + rest_total
    denominator = math.comb(all_total, top_total)
    return sum(math.comb(all_bad, count) * math.comb(all_total - all_bad, top_total - count)
               for count in range(max(0, top_total - (all_total - all_bad)), top_bad + 1)) / denominator


def percentile(values: list[float], fraction: float) -> float | None:
    return sorted(values)[int((len(values) - 1) * fraction)] if values else None


def analyze(session: Path) -> dict:
    audit = json.loads((session / "audit.json").read_text())
    if audit["coverage_status"] != "SIGNATURES_MATCH_INNER_SLOTS" or audit["event_decode_error_count"]:
        raise ValueError("MC-006 requires a covered, decoded cohort")
    flow = json.loads((session / "mc005-flow-result.json").read_text())
    if flow["score"] != "observed_buys_5s - observed_sells_5s":
        raise ValueError("flow score differs from frozen design")
    ranked_rows = [json.loads(line) for line in (
        session / "mc005-flow-rows.jsonl").read_text().splitlines()]
    observations = [json.loads(line) for line in (
        session / "observations.jsonl").read_text().splitlines()]
    creates = {row["signature"]: row for row in observations
               if row["event_type"] == "CreateEvent"}
    trades_by_mint: dict[str, list[dict]] = defaultdict(list)
    for row in observations:
        if row["event_type"] == "TradeEvent":
            trades_by_mint[row["mint"]].append(row)
    detailed = []
    for row in ranked_rows:
        created = creates[row["signature"]]
        start = datetime.fromisoformat(created["available_at"])
        end = start + timedelta(seconds=5)
        buys = [trade for trade in trades_by_mint[row["mint"]]
                if trade["quote_mint"] == NATIVE_QUOTE and not trade["mayhem_mode"]
                and trade["is_buy"] and start <= datetime.fromisoformat(trade["available_at"]) <= end]
        users = [trade["user"] for trade in buys if trade.get("user")]
        lag = (start - datetime.fromisoformat(created["event_time"])).total_seconds()
        detailed.append({**row, "create_event_timestamp_to_receipt_seconds": lag,
                         "first_five_second_buy_events": len(buys),
                         "first_five_second_distinct_event_users": len(set(users)),
                         "first_five_second_missing_event_users": len(buys) - len(users)})
    all_create_lags = [(datetime.fromisoformat(row["available_at"]) -
                        datetime.fromisoformat(row["event_time"])).total_seconds()
                       for row in creates.values()]
    minute_lags: dict[str, list[float]] = defaultdict(list)
    for row in creates.values():
        received = datetime.fromisoformat(row["available_at"])
        minute_lags[received.strftime("%Y-%m-%dT%H:%MZ")].append(
            (received - datetime.fromisoformat(row["event_time"])).total_seconds())

    def lag_summary(values: list[float]) -> dict:
        return {"n": len(values), "median": statistics.median(values) if values else None,
                "p90": percentile(values, 0.9), "above_5_seconds": sum(value > 5 for value in values),
                "above_10_seconds": sum(value > 10 for value in values),
                "max": max(values) if values else None}

    splits = {}
    for split in ("development", "evaluation"):
        rows = sorted((row for row in detailed if row["split"] == split),
                      key=lambda row: (-row["flow_score"], row["signature"]))
        top_count = math.ceil(len(rows) / 4)
        groups = {"top_quartile": rows[:top_count], "rest": rows[top_count:]}
        summary = {}
        for name, group in groups.items():
            known = [row for row in group if row["returns"]["155000"] is not None]
            unavailable = sum(row["exit_feasibility"] == "EXIT_UNAVAILABLE" for row in known)
            summary[name] = {"scored": len(group), "entry_known": len(known),
                             "exit_unavailable": unavailable,
                             "exit_unavailable_rate": unavailable / len(known) if known else None,
                             "exit_unavailable_exact_95_interval": exact_binomial_interval(
                                 unavailable, len(known)),
                             "median_distinct_event_buy_users_5s": statistics.median(
                                 row["first_five_second_distinct_event_users"] for row in group)
                             if group else None,
                             "median_buy_events_5s": statistics.median(
                                 row["first_five_second_buy_events"] for row in group)
                             if group else None,
                             "create_lag": lag_summary([
                                 row["create_event_timestamp_to_receipt_seconds"] for row in group])}
        top, rest = summary["top_quartile"], summary["rest"]
        summary["risk_difference_top_minus_rest"] = (
            top["exit_unavailable_rate"] - rest["exit_unavailable_rate"]
            if top["exit_unavailable_rate"] is not None and rest["exit_unavailable_rate"] is not None
            else None)
        summary["one_sided_fisher_exact_p_descriptive"] = fisher_lower_tail(
            top["exit_unavailable"], top["entry_known"],
            rest["exit_unavailable"], rest["entry_known"])
        splits[split] = summary
    evaluation_known = (splits["evaluation"]["top_quartile"]["entry_known"] +
                        splits["evaluation"]["rest"]["entry_known"])
    result = {"schema": "rocket.memecoin.mc006-diagnostics.v1",
              "full_create_lag": lag_summary(all_create_lags),
              "create_lag_by_receipt_minute": {name: lag_summary(values)
                                               for name, values in sorted(minute_lags.items())},
              "splits": splits,
              "minimum_risk_replication_gates": {
                  "evaluation_entry_known_at_least_30": evaluation_known >= 30,
                  "top_risk_lower_in_both_splits": all(
                      splits[name]["risk_difference_top_minus_rest"] is not None
                      and splits[name]["risk_difference_top_minus_rest"] < 0
                      for name in splits),
                  "fast_discovery_p90_at_most_5_seconds": (
                      percentile(all_create_lags, 0.9) is not None
                      and percentile(all_create_lags, 0.9) <= 5),
              },
              "event_user_caveat": "IDL event address, not a verified beneficial buyer."}
    (session / "mc006-diagnostic-rows.jsonl").write_text("".join(
        json.dumps(row, sort_keys=True) + "\n" for row in detailed))
    (session / "mc006-diagnostics.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.session), indent=2))
