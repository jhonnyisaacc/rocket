"""Experiment 0: no prediction, no model selection, no strategy PnL optimization."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from bisect import bisect_left
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from rocket.momentum.core import (
    DAY,
    CandidateEvent,
    aggregate_four_hours,
    candidates,
    dt,
    fingerprint,
    interval_groups,
    label,
    snapshot,
    spaced_events,
)
from rocket.momentum.source import load


def distribution(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"n": 0, "mean": None, "median": None, "p10": None, "p90": None}

    def quantile(p):
        pos = (len(values) - 1) * p
        lo, hi = math.floor(pos), math.ceil(pos)
        return values[lo] + (values[hi] - values[lo]) * (pos - lo)

    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "p10": quantile(0.1),
        "p90": quantile(0.9),
    }


def concentration(weights):
    positive = sorted((max(0.0, x) for x in weights), reverse=True)
    total = sum(positive)
    return {
        "kish_n": total * total / sum(x * x for x in positive) if total else 0,
        "top1_fraction": positive[0] / total if total else None,
        "top5_fraction": sum(positive[:5]) / total if total else None,
    }


def segment_legs(bars, events, *, audit=None):
    """Ex-post directional-change diagnostics; NEVER used for candidate labels/features."""
    scales = []
    for i, b in enumerate(bars):
        s = snapshot(bars[max(0, i - 180) : i + 1], b.end_time + 300_000, b.end_time)
        scales.append(s.sigma * math.sqrt(42) if s.sigma else None)
    valid = [i for i, s in enumerate(scales) if s]
    if not valid:
        if audit is not None:
            audit.update(
                algorithm="closed-4h-extremum-scale-v1",
                completed_legs=0,
                gap_censored_legs=[],
                censored_tail=None,
            )
        return []
    lo = hi = anchor = valid[0]
    direction, finished = 0, []
    gap_censored = []
    for i in range(valid[0] + 1, len(bars)):
        if scales[i] is None:
            if audit is not None and direction:
                gap_censored.append(
                    {
                        "direction": direction,
                        "start": bars[anchor].end_time,
                        "extremum": bars[hi if direction == 1 else lo].end_time,
                        "gap_observed_at": bars[i].end_time,
                        "censored": True,
                    }
                )
            direction, lo, hi, anchor = 0, i, i, i
            continue
        price = bars[i].close
        if direction == 0:
            if price < bars[lo].close:
                lo = i
            if price > bars[hi].close:
                hi = i
            if scales[lo] and math.log(price / bars[lo].close) >= scales[lo]:
                direction, anchor, hi = 1, lo, i
            elif scales[hi] and math.log(bars[hi].close / price) >= scales[hi]:
                direction, anchor, lo = -1, hi, i
        elif direction == 1:
            if price >= bars[hi].close:
                hi = i
            elif math.log(bars[hi].close / price) >= scales[hi]:
                finished.append((anchor, hi, 1, i))
                direction, anchor, lo = -1, hi, i
        else:
            if price <= bars[lo].close:
                lo = i
            elif math.log(price / bars[lo].close) >= scales[lo]:
                finished.append((anchor, lo, -1, i))
                direction, anchor, hi = 1, lo, i
    if audit is not None:
        audit.update(
            algorithm="closed-4h-extremum-scale-v1",
            completed_legs=len(finished),
            completed_leg_geometry=[
                {
                    "start": bars[start].end_time,
                    "end": bars[end].end_time,
                    "direction": side,
                    "start_price": bars[start].close,
                    "extremum_price": bars[end].close,
                    "anchor_scale_S": scales[start],
                    "extremum_reversal_scale_S": scales[end],
                    "magnitude_log": side * math.log(bars[end].close / bars[start].close),
                    "large": side * math.log(bars[end].close / bars[start].close)
                    >= 2 * scales[start],
                    "reversal_observed_at": bars[reversal].end_time,
                    "censored": False,
                }
                for start, end, side, reversal in finished
            ],
            gap_censored_legs=gap_censored,
            censored_tail={
                "direction": direction,
                "start": bars[anchor].end_time,
                "extremum": bars[hi if direction == 1 else lo].end_time,
                "censored": True,
            }
            if bars and direction
            else None,
        )
    legs = []
    for start, end, side, reversal in finished:
        scale = scales[start]
        magnitude = side * math.log(bars[end].close / bars[start].close)
        if not scale or magnitude < 2 * scale:
            continue
        confirm = next(
            (
                i
                for i in range(start + 1, end + 1)
                if side * math.log(bars[i].close / bars[start].close) >= scale
            ),
            None,
        )

        def consumed(index, end=end, side=side, start=start, magnitude=magnitude):
            if index is None or index > end:
                return 1.0
            return max(
                0.0, min(1.0, side * math.log(bars[index].close / bars[start].close) / magnitude)
            )

        causal = next(
            (
                e
                for e in events
                if e.direction == side
                and bars[start].end_time < e.data_cutoff <= bars[end].end_time
            ),
            None,
        )
        detect_index = next(
            (i for i in range(start, end + 1) if causal and bars[i].end_time == causal.data_cutoff),
            None,
        )
        legs.append(
            {
                "start": bars[start].end_time,
                "end": bars[end].end_time,
                "reversal_observed_at": bars[reversal].end_time,
                "direction": side,
                "magnitude": magnitude,
                "normalized_magnitude": magnitude / scale,
                "duration_hours": (end - start) * 4,
                "consumed_oracle": {
                    str(delay): consumed(confirm + delay // 4 if confirm is not None else None)
                    for delay in (0, 4, 8, 12)
                },
                "candidate_detected": causal is not None,
                "candidate_consumed": consumed(detect_index),
                "candidate_lead_hours": (
                    (bars[end].end_time - causal.data_cutoff) / 3_600_000 if causal else None
                ),
            }
        )
    return legs


def summarize(events, outcomes, side, years):
    pairs = [(e, outcomes[e.event_id]) for e in events if e.direction == side]
    complete = [(e, l) for e, l in pairs if l.outcome != "UNKNOWN"]
    successes = [(e, l) for e, l in complete if l.outcome.startswith("CONTINUES")]
    top_removed = sorted(complete, key=lambda pair: pair[1].mfe or 0, reverse=True)[5:]
    result = {
        "candidates": len(pairs),
        "fully_labeled": len(complete),
        "outcomes": dict(Counter(l.outcome for _, l in pairs)),
        "successes": len(successes),
        "candidates_per_year": len(pairs) / years,
        "by_year": dict(Counter(str(dt(e.data_cutoff).year) for e, _ in pairs)),
        "successful_by_year": dict(Counter(str(dt(e.data_cutoff).year) for e, _ in successes)),
        "success_concentration": concentration(
            list(Counter(dt(e.data_cutoff).year for e, _ in successes).values())
        ),
        "mfe_concentration": concentration([l.mfe for _, l in complete]),
    }
    for field in (
        "signed_return",
        "mfe",
        "mae",
        "mfe_normalized",
        "mae_normalized",
        "delay_4h_return",
    ):
        result[field] = distribution([getattr(l, field) for _, l in complete])
    result["duration_hours"] = distribution(
        [((l.barrier_time or l.label_end) - e.decision_time) / 3_600_000 for e, l in complete]
    )
    result["normalized_forward_return"] = distribution(
        [l.signed_return / e.scale for e, l in complete]
    )
    result["net_log_return_hurdles"] = {
        str(bp): distribution([l.signed_return - bp / 10_000 for _, l in complete])
        for bp in (20, 40, 80)
    }
    result["delayed_net_log_return_hurdles"] = {
        str(bp): distribution([l.delay_4h_return - bp / 10_000 for _, l in complete])
        for bp in (20, 40, 80)
    }
    result["top5_removed_return"] = distribution([l.signed_return for _, l in top_removed])
    return result


def run(root: Path, output: Path):
    hourly = load(root)
    bars = aggregate_four_hours(hourly)
    events, eligible = candidates(bars)
    independent = spaced_events(events)
    opens = [b.open_time for b in hourly]

    def forward(e: CandidateEvent, days=7, upper=2.0, lower=1.0):
        lo = bisect_left(opens, e.decision_time)
        hi = bisect_left(opens, e.data_cutoff + days * DAY)
        return label(e, hourly[lo:hi], days, upper, lower)

    primary = {e.event_id: forward(e) for e in events}
    years = (bars[-1].end_time - bars[0].open_time) / (365.25 * DAY)
    legs = segment_legs(bars, events)
    sides = {}
    for side, name in ((1, "UP"), (-1, "DOWN")):
        leg_side = [l for l in legs if l["direction"] == side]
        sides[name] = {
            "all_crossings": summarize(events, primary, side, years),
            "independent": summarize(independent, primary, side, years),
            "large_diagnostic_legs": len(leg_side),
            "oracle_consumed": {
                str(delay): distribution([l["consumed_oracle"][str(delay)] for l in leg_side])
                for delay in (0, 4, 8, 12)
            },
            "oracle_4h_half_remaining_fraction": (
                sum(l["consumed_oracle"]["4"] <= 0.5 for l in leg_side) / len(leg_side)
                if leg_side
                else None
            ),
            "candidate_detected_fraction": (
                sum(l["candidate_detected"] for l in leg_side) / len(leg_side) if leg_side else None
            ),
            "candidate_consumed": distribution([l["candidate_consumed"] for l in leg_side]),
            "candidate_lead_hours": distribution([l["candidate_lead_hours"] for l in leg_side]),
        }
    sensitivity = {}
    for days in (3, 7, 14):
        for upper, lower in ((2, 1), (1.6, 1), (2.4, 1), (2, 0.8), (2, 1.2)):
            labels = {e.event_id: forward(e, days, upper, lower) for e in independent}
            sensitivity[f"{days}d-u{upper}-l{lower}"] = {
                name: summarize(independent, labels, side, years)
                for side, name in ((1, "UP"), (-1, "DOWN"))
            }
    checks = {
        "five_years": years >= 5,
        "120_independent_labeled": sum(
            primary[e.event_id].outcome != "UNKNOWN" for e in independent
        )
        >= 120,
    }
    for name, side_stats in sides.items():
        sample = side_stats["independent"]
        counts = sample["successful_by_year"]
        checks[f"{name}_40_successes"] = sample["successes"] >= 40
        checks[f"{name}_three_annual_folds"] = (
            sum(int(year) >= 2021 and n >= 10 for year, n in counts.items()) >= 3
        )
        checks[f"{name}_year_concentration"] = (
            max(counts.values(), default=0) / sample["successes"] <= 0.4
            if sample["successes"]
            else False
        )
        remaining = side_stats["oracle_4h_half_remaining_fraction"]
        checks[f"{name}_oracle_latency"] = remaining is not None and remaining >= 0.5
    report = {
        "experiment": "MOM-000",
        "predictive_trials": 0,
        "contract": "btc-breakout-triple-barrier-v1",
        "plan_commit": "3272afc",
        "raw_hourly_rows": len(hourly),
        "raw_four_hour_rows": len(bars),
        "eligible_decisions": eligible,
        "candidate_crossings": len(events),
        "independent_candidates": len(independent),
        "overlap_components_7d": len(interval_groups(events, 7 * DAY)),
        "overlap_components_14d": len(interval_groups(events, 14 * DAY)),
        "overlap_interval_convention": "closed [decision_time, data_cutoff+horizon]; touching connects",
        "usable_years": years,
        "sides": sides,
        "sensitivity": sensitivity,
        "feasibility_checks": checks,
        "gate": "PERMITS_REGISTRATION" if all(checks.values()) else "STOP_INSUFFICIENT_FEASIBILITY",
        "labels_fingerprint": fingerprint([asdict(primary[e.event_id]) for e in events]),
        "diagnostic_warning": "Ex-post legs/oracle condition on realized large moves; not training labels.",
        "independence_warning": "Spacing is an independent-interval upper bound, not proof of stochastic independence.",
    }
    report["implementation_sha256"] = fingerprint(
        {
            name: fingerprint((Path(__file__).parent / name).read_text())
            for name in ("core.py", "source.py", "census.py")
        }
    )
    contract_file = Path("docs/research/momentum/MOMENTUM_EVENT_CONTRACT.md")
    report["contract_sha256"] = fingerprint(contract_file.read_text())
    manifest = json.loads(Path("docs/research/momentum/SOURCE_MANIFEST.json").read_text())
    report["source_manifest_sha256"] = manifest["manifest_sha256"]
    output.mkdir(parents=True, exist_ok=True)
    (output / "CENSUS.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "EPISODES_DIAGNOSTIC.json").write_text(json.dumps(legs, indent=2) + "\n")
    # Small transparent event table retained for diagnostics, never forecast input.
    (output / "EVENTS.json").write_text(
        json.dumps(
            [
                {
                    "event": asdict(e),
                    "label": asdict(primary[e.event_id]),
                    "independent": e in independent,
                }
                for e in events
            ],
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "candidate_crossings",
                    "independent_candidates",
                    "overlap_components_7d",
                    "overlap_components_14d",
                    "gate",
                    "feasibility_checks",
                )
            },
            indent=2,
        )
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.root, args.output)
