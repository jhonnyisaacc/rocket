"""Experiment MOM-000: momentum event census. No predictive model.

Consumes validated 4h + 1h bars, emits the contracted census report:
raw crossings, spaced independent set, label mix, durations, MAE/MFE,
signed end returns, cost-hurdle survival, one-close-delay sensitivity,
overlap components, Kish N, concentration, top-1/top-5, remove-top-5,
year clustering, ex-post legs, front-loading fractions, sensitivity
grid, and the gate decision. Deterministic JSON.
"""

from __future__ import annotations

import bisect
import math
from collections import Counter
from datetime import UTC, datetime

from rocket.momentum import contracts
from rocket.momentum.candidates import scan_crossings, space_candidates
from rocket.momentum.episodes import (
    front_loading_for_leg,
    kish_effective_n,
    overlap_components,
    segment_legs,
)
from rocket.momentum.labels import label_candidate, label_grid
from rocket.momentum.metrics import concentration


def _year(ms: int) -> int:
    return datetime.fromtimestamp(ms / 1000, UTC).year


def run_census(
    bars_4h: list[dict],
    bars_1h: list[dict],
    *,
    source_fingerprint: str = "",
    quarantined_rows: list | None = None,
) -> dict:
    crossings = scan_crossings(bars_4h)
    spaced_flags = space_candidates(crossings)
    spaced = [e for e in spaced_flags if e["independent"]]

    # Pre-slice the 1h tape per event (bisect on sorted opens) so labeling
    # scans ~14d of bars, not the full multi-year history, per call.
    ordered_1h = sorted(bars_1h, key=lambda b: b["open_ms"])
    opens_1h = [b["open_ms"] for b in ordered_1h]
    max_horizon_ms = max(contracts.HORIZON_PRIMARY_DAYS, *contracts.HORIZON_SENSITIVITY_DAYS)
    max_horizon_ms *= 24 * 3600 * 1000

    labeled, grid_outcomes = [], {}
    for event in spaced_flags:
        start = event["cutoff_ms"] + 3600 * 1000
        lo = bisect.bisect_left(opens_1h, start)
        hi = bisect.bisect_left(opens_1h, event["cutoff_ms"] + max_horizon_ms)
        tape = ordered_1h[lo:hi]
        lab = label_candidate(event, tape)
        labeled.append({**event, **lab})
        grid = label_grid(event, tape)
        grid_outcomes[event["cutoff_ms"]] = {k: v["outcome"] for k, v in grid.items()}

    report: dict = {
        "census": contracts.CENSUS_VERSION,
        "candidate_generator": contracts.CANDIDATE_GENERATOR_VERSION,
        "label_contract": contracts.LABEL_CONTRACT_VERSION,
        "source_fingerprint": source_fingerprint,
        "n_4h_bars": len(bars_4h),
        "n_1h_bars": len(bars_1h),
        "n_crossings": len(crossings),
        "n_spaced": len(spaced),
        "quarantined_rows": len(quarantined_rows or []),
        "quarantine_detail": list(quarantined_rows or []),
    }
    for side in contracts.DIRECTIONS:
        evs = [e for e in labeled if e["direction"] == side]
        ind = [e for e in evs if e["independent"]]
        ok = [e for e in ind if e["outcome"] == "CONTINUES"]
        outcomes = Counter(e["outcome"] for e in ind)
        mfes = [e["mfe_S"] for e in ind if e["mfe_S"] is not None]
        maes = [e["mae_S"] for e in ind if e["mae_S"] is not None]
        ends = [e["end_S"] for e in ind if e["end_S"] is not None]
        durations = [e["duration_bars"] for e in ind if e["duration_bars"] is not None]
        years = Counter(_year(e["cutoff_ms"]) for e in ind)
        year_success = Counter(_year(e["cutoff_ms"]) for e in ind if e["outcome"] == "CONTINUES")
        report[side] = {
            "crossings": len(evs),
            "independent": len(ind),
            "continues": len(ok),
            "fails": outcomes.get("FAILS", 0),
            "timeouts": outcomes.get("TIMEOUT", 0),
            "unknown": outcomes.get("UNKNOWN", 0),
            "success_rate": len(ok) / len(ind) if ind else None,
            "mfe_S_median": _median(mfes),
            "mae_S_median": _median(maes),
            "end_S_median": _median(ends),
            "duration_bars_median": _median([float(d) for d in durations]),
            "by_year": dict(sorted(years.items())),
            "by_year_success": dict(sorted(year_success.items())),
            "kish_N_years": kish_effective_n(list(years.values())),
            "concentration_mfe": concentration([e["mfe_log"] or 0.0 for e in ind]),
            "cost_hurdles": {
                f"{bp:g}bp": _hurdle_stats(ind, bp) for bp in contracts.COST_HURDLES_BP
            },
        }
    comps = overlap_components(crossings)
    report["overlap_components"] = {
        "n_components": len(comps),
        "largest": max((len(c) for c in comps), default=0),
        "singleton_share": sum(1 for c in comps if len(c) == 1) / max(len(comps), 1),
    }
    legs = segment_legs(bars_4h)
    large = [lg for lg in legs if lg["large"] and not lg["censored"]]
    fronts = {"UP": [], "DOWN": []}
    for leg in large:
        side = "UP" if leg["direction"] == 1 else "DOWN"
        fronts[side].append(front_loading_for_leg(leg, bars_4h))
    report["ex_post_legs"] = {
        "n_legs": len(legs),
        "n_large_uncensored": len(large),
        "front_loading": {
            side: {
                "n": len(rows),
                "frac_at_confirm_median": _median([r["fractions"][0] for r in rows if r.get("fractions")]),
                "frac_plus4h_median": _median([r["fractions"][1] for r in rows if r.get("fractions")]),
                "frac_plus8h_median": _median([r["fractions"][2] for r in rows if r.get("fractions")]),
                "frac_plus12h_median": _median([r["fractions"][3] for r in rows if r.get("fractions")]),
                "never_confirmed": sum(1 for r in rows if r.get("note") == "never-confirmed"),
            }
            for side, rows in fronts.items()
        },
    }
    grid_primary = Counter(v[f"{contracts.HORIZON_PRIMARY_DAYS}d_up2.0_lo1.0"] for v in grid_outcomes.values())
    report["sensitivity_primary_mix"] = dict(grid_primary)
    report["gate"] = evaluate_gate(report)
    return report


def _median(values: list[float]) -> float | None:
    vals = sorted(v for v in values if v is not None and math.isfinite(v))
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def _hurdle_stats(ind: list[dict], bp: float) -> dict:
    hurdle = bp / 10_000
    survived = sum(1 for e in ind if (e.get("end_log") or 0.0) > hurdle and e["outcome"] == "CONTINUES")
    return {"hurdle_bp": bp, "continues_above_hurdle": survived,
            "n_independent": len(ind)}


def evaluate_gate(report: dict) -> dict:
    """MOM-000 feasibility gates (frozen thresholds). All required."""
    checks = {}
    for side in contracts.DIRECTIONS:
        block = report[side]
        checks[f"{side}_independent_ge_40succ"] = (block["continues"] or 0) >= 40
        years = block["by_year"]
        top_year_share = max(years.values()) / max(sum(years.values()), 1) if years else 1.0
        checks[f"{side}_top_year_le_40pct"] = top_year_share <= 0.40
    checks["spaced_ge_120"] = (report["n_spaced"] or 0) >= 120
    folds_ok = True
    for side in contracts.DIRECTIONS:
        succ = report[side]["by_year_success"]
        good_years = sum(1 for y, c in succ.items() if c >= 10)
        if good_years < 3:
            folds_ok = False
    checks["three_annual_folds"] = folds_ok
    for side in ("UP", "DOWN"):
        fl = report["ex_post_legs"]["front_loading"][side]
        med = fl["frac_plus4h_median"]
        checks[f"{side}_frontload_ge_half_retained"] = med is not None and med <= 0.50
    passed = all(checks.values())
    return {"checks": checks, "permit_experiment_1": passed,
            "verdict": "PASS" if passed else "STOP"}
