"""MC-002 frozen five-second curve-progress baseline and costed quote proxy."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timedelta
from pathlib import Path

from rocket.research.memecoin_dataset import SnapshotError, build_snapshot
from rocket.research.pump_execution import CurveState, FeeSchedule, buy_exact_input, sell

NATIVE_QUOTE = "11111111111111111111111111111111"
SIZE_LAMPORTS = 10_000_000
NETWORK_COST_PER_LEG = 155_000
SLIPPAGE_BPS = 200
CHECKPOINT_SECONDS = 5
ENTRY_SECONDS = 7
EXIT_SECONDS = 67
IDL_REVISION = "81091419e4457566469d4e2a27f64ed84d42419c"


class EntryQuoteError(ValueError):
    pass


class ExitQuoteError(ValueError):
    def __init__(self, reason: str, entry_quote: dict[str, int]):
        super().__init__(reason)
        self.entry_quote = entry_quote


def stamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def latest_before(rows: list[dict], target: datetime) -> dict | None:
    eligible = [row for row in rows if stamp(row["available_at"]) <= target]
    return max(eligible, key=lambda row: (row["available_at"], row["slot"],
                                           row.get("transaction_index") or -1,
                                           row["log_index"])) if eligible else None


def fee_schedule(row: dict) -> FeeSchedule:
    return FeeSchedule(row["fee_basis_points"], row["creator_fee_basis_points"],
                       row["creator"] != NATIVE_QUOTE)


def curve_state(row: dict) -> CurveState:
    return CurveState(row["virtual_sol_reserves"], row["virtual_token_reserves"],
                      row["real_sol_reserves"], row["real_token_reserves"])


def feature(name: str, value: float, source: dict) -> dict:
    return {"name": name, "value": value, "event_time": source["event_time"],
            "available_at": source["available_at"],
            "source_ref": f"{source['signature']}:{source['event_type']}",
            "source_hash": source["source_hash"]}


def proxy_return(entry: dict, exit_state: dict) -> dict:
    try:
        bought = buy_exact_input(curve_state(entry), SIZE_LAMPORTS, fee_schedule(entry))
    except ValueError as exc:
        raise EntryQuoteError(str(exc)) from exc
    stressed_tokens = bought["tokens"] * (10_000 - SLIPPAGE_BPS) // 10_000
    try:
        exited = sell(curve_state(exit_state), stressed_tokens, fee_schedule(exit_state))
    except ValueError as exc:
        raise ExitQuoteError(str(exc), bought) from exc
    stressed_cash = exited["cash"] * (10_000 - SLIPPAGE_BPS) // 10_000
    net = stressed_cash - bought["cash"] - 2 * NETWORK_COST_PER_LEG
    return {"entry_quote": bought, "exit_quote": exited,
            "stressed_entry_tokens": stressed_tokens,
            "stressed_exit_cash_lamports": stressed_cash,
            "net_quote_proxy_lamports": net,
            "net_quote_proxy_return": net / (bought["cash"] + NETWORK_COST_PER_LEG)}


def evaluate_session(session: Path) -> dict:
    audit = json.loads((session / "audit.json").read_text())
    if audit["coverage_status"] != "SIGNATURES_MATCH_INNER_SLOTS" or audit["event_decode_error_count"]:
        raise ValueError("covered, strictly decoded inner slots required")
    if audit["event_transaction_identity_mismatches"] or audit[
        "created_mint_trade_state_continuity"]["native_nonmayhem_fail"] or audit[
        "native_nonmayhem_quote_validation"]["fail"]:
        raise ValueError("protocol identity, state continuity or quote validation failed")
    rows = [json.loads(line) for line in (session / "observations.jsonl").read_text().splitlines()]
    inner_start, inner_end = audit["inner_slot_bounds"]
    covered = [row for row in rows if inner_start <= row["slot"] <= inner_end]
    if not covered:
        raise ValueError("no covered observations")
    coverage_end = max(stamp(row["available_at"]) for row in covered)
    creates = sorted((row for row in covered if row["event_type"] == "CreateEvent"),
                     key=lambda row: (row["available_at"], row["signature"]))
    universe = []
    snapshots = []
    for created in creates:
        mint = created["mint"]
        t0 = stamp(created["available_at"])
        record = {"mint": mint, "signature": created["signature"], "slot": created["slot"],
                  "created_available_at": created["available_at"],
                  "quote_mint": created["quote_mint"],
                  "mayhem": created["is_mayhem_mode"],
                  "holder_reward": created["is_holder_reward"],
                  "status": "EXCLUDED", "reason": None, "split": None,
                  "score": None, "outcome": None}
        universe.append(record)
        if created["quote_mint"] != NATIVE_QUOTE:
            record["reason"] = "NON_NATIVE_QUOTE"
            continue
        if created["is_mayhem_mode"]:
            record["reason"] = "MAYHEM_UNSUPPORTED"
            continue
        if t0 + timedelta(seconds=EXIT_SECONDS) > coverage_end:
            record["reason"] = "EXIT_OUTSIDE_COVERED_CAPTURE"
            continue
        trades = [row for row in covered if row["event_type"] == "TradeEvent"
                  and row["mint"] == mint and row["quote_mint"] == NATIVE_QUOTE
                  and not row["mayhem_mode"] and stamp(row["available_at"]) >= t0]
        decision = t0 + timedelta(seconds=CHECKPOINT_SECONDS)
        early = [row for row in trades if stamp(row["available_at"]) <= decision]
        last = latest_before(trades, decision) or created
        progress = ((created["real_token_reserves"] - last["real_token_reserves"])
                    / created["real_token_reserves"])
        buys = sum(row["is_buy"] for row in early)
        sells = len(early) - buys
        aggregate_hash = hashlib.sha256("".join(
            row["event_sha256"] for row in [created, *early]).encode()).hexdigest()
        observed_flow = {**created, "event_time": last["event_time"],
                         "available_at": decision.isoformat(),
                         "signature": f"observed-flow:{mint}",
                         "event_type": "Aggregate", "source_hash": aggregate_hash}
        try:
            snapshot = build_snapshot(
                {"chain_id": "solana:mainnet", "mint": mint},
                [feature("curve_progress_5s", progress, last),
                 feature("observed_buys_5s", buys, observed_flow),
                 feature("observed_sells_5s", sells, observed_flow),
                 feature("real_token_reserves", last["real_token_reserves"], last),
                 feature("virtual_sol_reserves", last["virtual_sol_reserves"], last)],
                decision_time=decision, lifecycle_stage="bonding_curve",
                discovery_source="pump_create_event:logsSubscribe",
                protocol_version=f"pump-idl:{IDL_REVISION}",
                fee_model_version="as-of-trade-bps-v1")
        except SnapshotError as exc:
            record["reason"] = f"SNAPSHOT_INVALID:{exc}"
            continue
        snapshot["quote_mint"] = NATIVE_QUOTE
        snapshots.append(snapshot)
        record["score"] = progress
        record["snapshot_fingerprint"] = snapshot["fingerprint"]
        entry = latest_before(trades, t0 + timedelta(seconds=ENTRY_SECONDS))
        exit_state = latest_before(trades, t0 + timedelta(seconds=EXIT_SECONDS))
        if entry is None:
            record["status"], record["reason"] = "CENSORED", "NO_AS_OF_ENTRY_FEE_STATE"
            continue
        if exit_state is None:
            record["status"], record["reason"] = "CENSORED", "NO_AS_OF_EXIT_STATE"
            continue
        try:
            outcome = proxy_return(entry, exit_state)
        except EntryQuoteError as exc:
            record["status"], record["reason"] = "NO_FILL", str(exc)
            continue
        except ExitQuoteError as exc:
            record["status"], record["reason"] = "CENSORED", f"EXIT_UNAVAILABLE:{exc}"
            record["entry_quote"] = exc.entry_quote
            record["entry_state_signature"] = entry["signature"]
            record["exit_state_signature"] = exit_state["signature"]
            continue
        record["status"] = "QUOTED"
        record["outcome"] = outcome
        record["entry_state_signature"] = entry["signature"]
        record["exit_state_signature"] = exit_state["signature"]

    qualifying = [row for row in universe if row["score"] is not None]
    boundary = math.ceil(0.7 * len(qualifying))
    for index, row in enumerate(qualifying):
        row["split"] = "development" if index < boundary else "evaluation"

    def split_metrics(split: str) -> dict:
        all_rows = [row for row in qualifying if row["split"] == split]
        ranked = sorted(all_rows, key=lambda row: (-row["score"], row["signature"]))
        top_count = max(1, math.ceil(len(ranked) / 4)) if ranked else 0
        top = ranked[:top_count]
        quoted = [row for row in all_rows if row["status"] == "QUOTED"]
        top_quoted = [row for row in top if row["status"] == "QUOTED"]
        def values(group: list[dict]) -> dict:
            returns = [row["outcome"]["net_quote_proxy_return"] for row in group]
            return {"n": len(returns), "mean": statistics.mean(returns) if returns else None,
                    "median": statistics.median(returns) if returns else None,
                    "positive": sum(value > 0 for value in returns)}
        return {"eligible": len(all_rows), "quoted": len(quoted), "top_quartile_size": top_count,
                "top_quartile_quoted": len(top_quoted), "all_quoted_returns": values(quoted),
                "top_quoted_returns": values(top_quoted),
                "score_ties": len({row["score"] for row in all_rows}) < len(all_rows),
                "censored": sum(row["status"] == "CENSORED" for row in all_rows),
                "no_fill": sum(row["status"] == "NO_FILL" for row in all_rows)}

    result = {
        "schema": "rocket.memecoin.mc002-result.v1",
        "capture_manifest_sha256": audit["capture_manifest_sha256"],
        "audit_sha256": hashlib.sha256((session / "audit.json").read_bytes()).hexdigest(),
        "feature_checkpoint_seconds": CHECKPOINT_SECONDS,
        "entry_seconds": ENTRY_SECONDS,
        "exit_seconds": EXIT_SECONDS,
        "size_lamports": SIZE_LAMPORTS,
        "slippage_bps_each_leg": SLIPPAGE_BPS,
        "network_cost_lamports_each_leg": NETWORK_COST_PER_LEG,
        "universe_count": len(universe),
        "status_counts": {status: sum(row["status"] == status for row in universe)
                          for status in ("EXCLUDED", "CENSORED", "NO_FILL", "QUOTED")},
        "reason_counts": {reason: sum(row["reason"] == reason for row in universe)
                          for reason in sorted({row["reason"] for row in universe if row["reason"]})},
        "development": split_metrics("development"),
        "evaluation": split_metrics("evaluation"),
        "conclusion": "Descriptive costed quote proxy only; execution and significance remain unproven.",
    }
    (session / "snapshots.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                                   for row in snapshots))
    (session / "universe.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                                  for row in universe))
    (session / "mc002-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(evaluate_session(arguments.session), indent=2))
