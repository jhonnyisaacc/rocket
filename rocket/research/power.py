"""Synthetic-only gate feasibility; input is structural data, never real outcomes.

No I/O, network, market-data imports or official scorer call exists in this module.
All outcomes, features, forecasts and paths below are freshly simulated.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import UTC, datetime
from functools import lru_cache

import numpy as np

from rocket.research.governance import GateError

SCHEMA = "rocket.power.geometry.v1"
ROW_KEYS = {"id", "decision_time", "cutoff", "direction", "scale", "year", "fold",
            "component_7d", "component_14d", "spaced", "horizon_supported"}
PROVENANCE_KEYS = {"source_revision", "causal_core_sha256", "source_parser_sha256", "source_files",
                   "real_outcomes_accessed", "feature_completeness", "coverage_assumption_start",
                   "generator", "intervals"}
EFFECTS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40)
SCENARIOS = ("independent", "clustered", "heavy_tailed", "up_stronger", "down_stronger")
GATES = ("readiness", "primary_information", "incremental_information", "spaced_consistency",
         "fold_consistency", "score_monotonicity", "economic_evidence", "adversity",
         "robustness", "concentration", "full_pass", "full_pass_without_adversity")
DAY = 86_400_000


def validate_geometry(value):
    if not isinstance(value, dict) or set(value) != {"schema", "provenance", "rows"} or value["schema"] != SCHEMA:
        raise GateError("Strict structural geometry schema required")
    provenance = value["provenance"]
    if set(provenance) != PROVENANCE_KEYS or provenance["real_outcomes_accessed"] is not False:
        raise GateError("Outcome-free structural provenance required")
    if not isinstance(value["rows"], list) or not value["rows"]:
        raise GateError("Nonempty structural population required")
    seen, previous = set(), -1
    for row in value["rows"]:
        if set(row) != ROW_KEYS:
            raise GateError("Unknown geometry column: real outcomes/features are forbidden")
        if not isinstance(row["id"], str) or row["id"] in seen:
            raise GateError("Unique candidate identity required")
        seen.add(row["id"])
        if type(row["direction"]) is not int or row["direction"] not in (-1, 1):
            raise GateError("Known candidate direction required")
        for key in ("decision_time", "cutoff", "year", "component_7d", "component_14d"):
            if type(row[key]) is not int:
                raise GateError("Integer structural clock/component required")
        if row["decision_time"] <= previous or row["decision_time"] != row["cutoff"] + 300_000:
            raise GateError("Ordered causal decision clocks required")
        previous = row["decision_time"]
        year = datetime.fromtimestamp(row["decision_time"] / 1000, UTC).year
        if row["year"] != year or row["fold"] != (year if year in (2023, 2024, 2025) else None):
            raise GateError("Fixed annual folds required")
        if type(row["scale"]) not in (int, float) or not math.isfinite(row["scale"]) or row["scale"] <= 0:
            raise GateError("Finite causal scale required")
        if any(type(row[k]) is not bool for k in ("spaced", "horizon_supported")):
            raise GateError("Explicit structural membership required")
    for days in (7, 14):
        end, group = -1, -1
        for row in value["rows"]:
            if row["decision_time"] > end:
                group += 1
            if row[f"component_{days}d"] != group:
                raise GateError("Component geometry differs from frozen interval semantics")
            end = max(end, row["cutoff"] + days * DAY)
    next_time = -1
    for row in value["rows"]:
        expected = row["decision_time"] >= next_time
        if row["spaced"] != expected:
            raise GateError("Spaced identities differ from global 14d cooldown")
        if expected:
            next_time = row["decision_time"] + 14 * DAY
    return value


def weights(groups):
    _, inverse, counts = np.unique(groups, return_inverse=True, return_counts=True)
    w = 1.0 / counts[inverse]
    return w / w.sum()


def corr(y, forecast, w):
    cy, cf = y - w @ y, forecast - w @ forecast
    denominator = math.sqrt(float(w @ cy**2) * float(w @ cf**2))
    return float(w @ (cy * cf)) / denominator if denominator > 0 else -math.inf


def skill(y, forecast, benchmark, w):
    denominator = float(w @ (y - benchmark)**2)
    return 1 - float(w @ (y - forecast)**2) / denominator if denominator > 0 else -math.inf


def weighted_quantile(values, w, p):
    order = np.argsort(values, kind="stable")
    index = np.searchsorted(np.cumsum(w[order]) / w.sum(), p, side="left")
    return values[order[min(index, len(order) - 1)]]


def ridge(x, y, direction, w, xt, dt, columns):
    """Two unpenalized direction intercepts, weighted training standardization, alpha=1."""
    if not columns:
        means = {side: np.average(y[direction == side], weights=w[direction == side]) for side in (-1, 1)}
        return np.array([means[d] for d in direction]), np.array([means[d] for d in dt])
    x, xt = x[:, columns], xt[:, columns]
    mu = w @ x
    sd = np.sqrt(w @ (x - mu)**2)
    z, zt = (x - mu) / np.where(sd > 0, sd, 1), (xt - mu) / np.where(sd > 0, sd, 1)
    z[:, sd == 0], zt[:, sd == 0] = 0, 0
    design = np.column_stack((direction == 1, direction == -1, z)).astype(float)
    test = np.column_stack((dt == 1, dt == -1, zt)).astype(float)
    penalty = np.diag([0., 0.] + [1.] * len(columns))
    beta = np.linalg.solve(design.T @ (w[:, None] * design) + penalty, design.T @ (w * y))
    return design @ beta, test @ beta


@lru_cache(maxsize=256)
def bootstrap_counts(components, draws):
    rng = np.random.default_rng(20261002)
    return rng.multinomial(components, np.full(components, 1 / components), size=draws).astype(float)


class ClusterDraws:
    """Aggregate sufficient statistics before bootstrap multiplication."""

    def __init__(self, groups, draws):
        unique, self.inverse = np.unique(groups, return_inverse=True)
        self.counts = bootstrap_counts(len(unique), draws)

    def sums(self, *values):
        aggregated = np.column_stack([np.bincount(self.inverse, weights=v, minlength=self.counts.shape[1]) for v in values])
        return self.counts @ aggregated


def bootstrap_multiplicity(groups, draws):
    # Counts preserve duplicated clusters as distinct replicates, rather than deduplicating.
    return ClusterDraws(groups, draws)


def lower(values):
    good = np.isfinite(values)
    values = np.where(good, values, -np.inf)
    if good.mean() < 0.95:
        return -math.inf
    # Fixed linear empirical quantile; handle infinite endpoint without NaN arithmetic.
    values.sort()
    position = 0.025 * (len(values) - 1)
    lo, hi = math.floor(position), math.ceil(position)
    if not np.isfinite(values[lo]) or not np.isfinite(values[hi]):
        return -math.inf
    return float(values[lo] + (values[hi] - values[lo]) * (position - lo))


def boot_corr(y, f, multiplicity, base):
    sums = multiplicity.sums(base, base*y, base*f, base*y**2, base*f**2, base*y*f)
    sums /= sums[:, 0, None]
    ey, ef = sums[:, 1], sums[:, 2]
    denominator = np.sqrt(np.maximum(0, sums[:, 3] - ey**2) * np.maximum(0, sums[:, 4] - ef**2))
    with np.errstate(divide="ignore", invalid="ignore"):
        return (sums[:, 5] - ey * ef) / denominator


def boot_skill(y, f, b, multiplicity, base):
    sums = multiplicity.sums(base*(y-f)**2, base*(y-b)**2)
    with np.errstate(divide="ignore", invalid="ignore"):
        return 1 - sums[:, 0] / sums[:, 1]


def boot_mean(y, selected, multiplicity):
    sums = multiplicity.sums(np.where(selected, y, 0), selected.astype(float))
    with np.errstate(divide="ignore", invalid="ignore"):
        return sums[:, 0] / sums[:, 1]


def interval_probability(passed, n):
    """Wilson 95% Monte Carlo uncertainty, including zero successes."""
    p, z = passed / n, 1.959963984540054
    center = (p + z*z/(2*n)) / (1 + z*z/n)
    radius = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return {"probability": p, "passed": passed, "draws": n,
            "mc_95_interval": [max(0, center-radius), min(1, center+radius)]}


def structural_summary(geometry):
    rows = geometry["rows"]
    start = int(datetime.fromisoformat(geometry["provenance"]["coverage_assumption_start"]).timestamp()*1000)
    summary = {"population": len(rows), "spaced": sum(r["spaced"] for r in rows),
               "components": {str(d): len({r[f"component_{d}d"] for r in rows}) for d in (7, 14)},
               "frequency_by_year": dict(sorted(Counter(r["year"] for r in rows).items())), "folds": {}}
    for year in (2023, 2024, 2025):
        origin = int(datetime(year, 1, 1, tzinfo=UTC).timestamp()*1000)
        complete = [r for r in rows if r["decision_time"] >= start and r["horizon_supported"]]
        train = [r for r in complete if r["decision_time"] < origin-14*DAY and r["cutoff"]+7*DAY+300_000 < origin]
        test = [r for r in complete if r["fold"] == year]
        preceding = int(datetime(year-1, 1, 1, tzinfo=UTC).timestamp()*1000)
        trailing = [r for r in train if r["spaced"] and r["decision_time"] >= preceding]
        summary["folds"][str(year)] = {"train": len(train), "train_spaced": sum(r["spaced"] for r in train),
            "test": len(test), "test_spaced": sum(r["spaced"] for r in test), "annual_cap": len(trailing)//4,
            "components_14d": len({r["component_14d"] for r in test}), "trailing_train_spaced": len(trailing)}
    summary["maximum_alerts"] = sum(f["annual_cap"] for f in summary["folds"].values())
    summary["geometry_can_meet_8_alerts"] = summary["maximum_alerts"] >= 8
    return summary


def synthetic_trial(geometry, effect, scenario, missingness, seed, bootstrap_draws=2000):
    rows, n = geometry["rows"], len(geometry["rows"])
    rng = np.random.default_rng(seed)
    direction = np.array([r["direction"] for r in rows])
    time = np.array([r["decision_time"] for r in rows])
    cutoff = np.array([r["cutoff"] for r in rows])
    years = np.array([r["year"] for r in rows])
    spaced = np.array([r["spaced"] for r in rows])
    g7 = np.array([r["component_7d"] for r in rows])
    g14 = np.array([r["component_14d"] for r in rows])
    scale = np.array([r["scale"] for r in rows])
    coverage_start = int(datetime.fromisoformat(geometry["provenance"]["coverage_assumption_start"]).timestamp()*1000)
    available = (time >= coverage_start) & np.array([r["horizon_supported"] for r in rows]) & (rng.random(n) >= missingness)
    x = math.sqrt(.75)*rng.normal(size=(n, 6)) + .5*rng.normal(size=(n, 1))
    # Balanced information in Tier A and Tier B, not calibrated from real associations.
    beta = np.array([1, -1, 1, 1, -1, 1], dtype=float)
    beta /= math.sqrt(.75*(beta@beta) + .25*beta.sum()**2)
    oracle = x @ beta
    noise = rng.normal(size=n)
    if scenario == "clustered":
        _, group = np.unique(g14, return_inverse=True)
        noise = math.sqrt(.5)*noise + math.sqrt(.5)*rng.normal(size=group.max()+1)[group]
    elif scenario == "heavy_tailed":
        noise = rng.standard_t(3, size=n) / math.sqrt(3)
    strengths = np.full(n, effect)
    if scenario in ("up_stronger", "down_stronger"):
        strong = 1 if scenario == "up_stronger" else -1
        factors = np.where(direction == strong, 1.5, .5)
        factors /= math.sqrt(float(np.mean(factors**2)))
        strengths *= factors
        noise *= np.where(direction == strong, .8, 1.2)
    y = strengths*oracle + np.sqrt(1-strengths**2)*noise
    forecasts = np.full((4, n), np.nan)
    alerts = np.zeros((4, n), dtype=bool)
    buckets = np.full(n, -1)
    readiness, caps = True, []
    for year in (2023, 2024, 2025):
        origin = int(datetime(year, 1, 1, tzinfo=UTC).timestamp()*1000)
        train = available & (time < origin-14*DAY) & (cutoff+7*DAY+300_000 < origin)
        test = available & (years == year)
        ti, oi = np.flatnonzero(train), np.flatnonzero(test)
        readiness &= (origin-coverage_start >= 730*DAY and len(ti) >= 50 and (train & spaced).sum() >= 20
                      and all((train & (direction == side)).sum() >= 10 for side in (-1, 1))
                      and len(oi) >= 20 and len(np.unique(g14[test])) >= 5
                      and all((test & (direction == side)).any() for side in (-1, 1)))
        if not len(ti) or not len(oi) or len(np.unique(direction[train])) < 2:
            return None
        # Rebuild training components from admitted mature prefix (no future membership).
        training_groups, end, group = [], -1, -1
        for index in ti:
            if time[index] > end:
                group += 1
            training_groups.append(group)
            end = max(end, cutoff[index]+7*DAY)
        tw = weights(np.array(training_groups))
        cap = int((train & spaced & (time >= int(datetime(year-1, 1, 1, tzinfo=UTC).timestamp()*1000))).sum())//4
        caps.append(cap)
        for model, columns in enumerate(([], [1], [0, 1, 2], list(range(6)))):
            fitted, forecasts[model, test] = ridge(x[train], y[train], direction[train], tw, x[test], direction[test], columns)
            st = spaced[train]
            candidates = oi[spaced[test]]
            if model == 0:
                selected = candidates[3::4][:cap]
            elif st.any():
                threshold = weighted_quantile(fitted[st], np.ones(st.sum()), .75)
                selected = candidates[forecasts[model, candidates] > threshold][:cap]
            else:
                selected = []
            alerts[model, selected] = True
            if model == 3:
                cuts = [weighted_quantile(fitted, tw, p) for p in (1/3, 2/3)]
                buckets[test] = np.searchsorted(cuts, forecasts[model, test], side="left")
    oos = available & np.isin(years, (2023, 2024, 2025))
    readiness &= len(np.unique(g14[oos])) >= 15 and (oos & spaced).sum() >= 25
    indices = np.flatnonzero(oos)
    y, f, b, b0, b1 = y[oos], forecasts[3, oos], forecasts[2, oos], forecasts[0, oos], forecasts[1, oos]
    g7, g14, year, side, scale, bins = g7[oos], g14[oos], years[oos], direction[oos], scale[oos], buckets[oos]
    a, a_tier, a_b0 = alerts[3, oos], alerts[2, oos], alerts[0, oos]
    w = weights(g7)
    multipliers = [bootstrap_multiplicity(g, bootstrap_draws) for g in (g7, g14)]
    primary = corr(y, f, w) >= .1
    if primary:
        primary = all(lower(boot_corr(y, f, mult, w)) > 0 for mult in multipliers)
    incremental = skill(y, f, b, w) >= .05 and skill(y, f, b0, w) >= .05 and skill(y, f, b1, w) >= 0
    if incremental:
        incremental = all(lower(boot_skill(y, f, b, mult, w)) > 0 for mult in multipliers)
    sm = spaced[indices]
    sw = np.full(sm.sum(), 1/sm.sum()) if sm.any() else np.array([])
    spaced_ok = bool(sm.any() and corr(y[sm], f[sm], sw) > 0
                     and skill(y[sm], f[sm], b[sm], sw) >= 0 and skill(y[sm], f[sm], b0[sm], sw) >= 0)
    folds_ok = all(corr(y[year == yr], f[year == yr], weights(g7[year == yr])) > 0
                   and skill(y[year == yr], f[year == yr], b[year == yr], weights(g7[year == yr])) > 0 for yr in (2023, 2024, 2025))
    mono = all((bins == k).any() for k in range(3))
    if mono:
        means = [np.average(y[bins == k], weights=w[bins == k]) for k in range(3)]
        mono = means[0] < means[1] < means[2]
        if mono:
            for mult in multipliers:
                sums = mult.sums(w*np.where(bins == 2, y, 0), w*(bins == 2),
                                 w*np.where(bins == 0, y, 0), w*(bins == 0))
                with np.errstate(divide="ignore", invalid="ignore"):
                    high = sums[:, 0]/sums[:, 1]
                    low = sums[:, 2]/sums[:, 3]
                mono &= lower(high-low) > 0
    count_gates = {"at_least_8_alerts": bool(a.sum() >= 8),
                   "at_least_2_per_fold": all((a & (year == yr)).sum() >= 2 for yr in (2023, 2024, 2025)),
                   "at_least_2_per_direction": all((a & (side == d)).sum() >= 2 for d in (-1, 1))}
    cardinality = all(count_gates.values())
    components = np.unique(g14)
    influence = np.array([abs(np.sum(w[g14 == group]*((y[g14 == group]-b[g14 == group])**2-(y[g14 == group]-f[g14 == group])**2))) for group in components])
    removed = components[np.argsort(-influence, kind="stable")[:5]]
    robustness_masks = [year != yr for yr in (2023, 2024, 2025)] + [~np.isin(g14, removed)]
    information_robust = [mask.any() and corr(y[mask], f[mask], weights(g7[mask])) > 0
                         and skill(y[mask], f[mask], b[mask], weights(g7[mask])) > 0 for mask in robustness_masks]
    economic_results = []
    for drift in (0., .10, .25):
        net = scale*(y+drift)-.004
        econ = bool(cardinality and net[a].mean() > 0 and a_tier.any() and a_b0.any()
                    and net[a].mean() > net[a_tier].mean() and net[a].mean() > net[a_b0].mean())
        if econ:
            econ = all(lower(boot_mean(net, a, mult)) > 0 for mult in multipliers)
        robustness_parts = [bool(info and (a & mask).any() and net[a & mask].mean() > 0)
                            for info, mask in zip(information_robust, robustness_masks, strict=True)]
        robust = all(robustness_parts)
        positive = np.where(a, np.maximum(net, 0), 0)
        total = positive.sum()
        by_year = np.array([positive[year == yr].sum() for yr in (2023, 2024, 2025)])
        by_group = np.array([positive[g14 == group].sum() for group in components])
        concentration = bool(total > 0 and by_year.max()/total <= .5 and by_group.max()/total <= .25
                             and np.sort(by_group)[-5:].sum()/total <= .6)
        diagnostic_gates = {"largest_year_at_most_50pct": bool(total > 0 and by_year.max()/total <= .5),
                            "largest_component_at_most_25pct": bool(total > 0 and by_group.max()/total <= .25),
                            "top_5_components_at_most_60pct": bool(total > 0 and np.sort(by_group)[-5:].sum()/total <= .6),
                            "at_least_9_positive_components": bool((by_group > 0).sum() >= 9),
                            "leave_one_year_out": all(robustness_parts[:3]),
                            "remove_5_influential_components": robustness_parts[3]}
        # Hourly synthetic bridges; never substitute real excursions or calibrate their scale.
        adversity = False
        if a.any():
            bridge_rng = np.random.default_rng(seed+991)
            increments = bridge_rng.normal(size=(a.sum(), 167))/math.sqrt(167)
            path = np.cumsum(increments, axis=1)
            fractions = np.arange(1, 168)/167
            bridge = path-path[:, -1, None]*fractions
            path = (y[a]+drift)[:, None]*fractions+bridge
            mae = np.maximum(0, -path.min(axis=1))
            adversity = bool(np.quantile(mae, .5, method="linear") < 1 and np.quantile(mae, .9, method="linear") < 2)
        gates = dict(zip(GATES[:6], (bool(readiness), bool(primary), bool(incremental), spaced_ok, bool(folds_ok), bool(mono)), strict=True))
        gates.update(economic_evidence=econ, adversity=adversity, robustness=robust, concentration=concentration)
        gates["full_pass_without_adversity"] = all(v for k, v in gates.items() if k != "adversity")
        gates["full_pass"] = gates["full_pass_without_adversity"] and adversity
        economic_results.append({"drift_S": drift, "gates": gates, "diagnostic_gates": diagnostic_gates,
                                 "positive_components": int((by_group > 0).sum())})
    return {"economics": economic_results, "alerts": int(a.sum()), "caps": caps,
            "cardinality_pass": bool(cardinality), "oos_r": corr(y, f, w),
            "count_gates": count_gates,
            "alerts_by_fold": [int((a & (year == yr)).sum()) for yr in (2023, 2024, 2025)],
            "alerts_by_direction": [int((a & (side == d)).sum()) for d in (1, -1)]}


def run(geometry, draws=2000, bootstrap_draws=2000, progress=None):
    validate_geometry(geometry)
    results = []
    for scenario_index, scenario in enumerate(SCENARIOS):
        for missingness in (0., .10):
            for effect in EFFECTS:
                counts = [Counter() for _ in range(3)]
                diagnostic_counts = [Counter() for _ in range(3)]
                positive_components = [0, 0, 0]
                count_totals, fold_totals, direction_totals = Counter(), np.zeros(3), np.zeros(2)
                alert_total, cap_total, cardinality, correlations = 0, 0, 0, []
                for draw in range(draws):
                    # Common random numbers across effect/economic/missingness regimes.
                    seed = 20261005 + scenario_index*1_000_000 + draw
                    result = synthetic_trial(geometry, effect, scenario, missingness, seed, bootstrap_draws)
                    if result is None:
                        continue
                    alert_total += result["alerts"]
                    cap_total += sum(result["caps"])
                    cardinality += result["cardinality_pass"]
                    count_totals.update({k: int(v) for k, v in result["count_gates"].items()})
                    fold_totals += result["alerts_by_fold"]
                    direction_totals += result["alerts_by_direction"]
                    correlations.append(result["oos_r"])
                    for index, economy in enumerate(result["economics"]):
                        counts[index].update({gate: int(passed) for gate, passed in economy["gates"].items()})
                        diagnostic_counts[index].update({gate: int(passed) for gate, passed in economy["diagnostic_gates"].items()})
                        positive_components[index] += economy["positive_components"]
                for index, drift in enumerate((0., .10, .25)):
                    probabilities = {gate: interval_probability(counts[index][gate], draws) for gate in GATES}
                    marginal_binding = min(GATES[:10], key=lambda gate: probabilities[gate]["probability"])
                    results.append({"scenario": scenario, "missingness": missingness, "synthetic_r": effect,
                        "economic_drift_S": drift, "probabilities": probabilities,
                        "binding_gate_by_marginal_probability": marginal_binding,
                        "mean_alerts": alert_total/draws, "mean_total_cap": cap_total/draws,
                        "alert_cardinality": interval_probability(cardinality, draws),
                        "alert_minima": {k: interval_probability(v, draws) for k, v in count_totals.items()},
                        "mean_alerts_by_fold": (fold_totals/draws).tolist(),
                        "mean_alerts_by_direction_up_down": (direction_totals/draws).tolist(),
                        "diagnostic_probabilities": {k: interval_probability(v, draws) for k, v in diagnostic_counts[index].items()},
                        "mean_positive_components": positive_components[index]/draws,
                        "mean_fitted_oos_r": float(np.mean(correlations)) if correlations else None})
                if progress:
                    progress(scenario, missingness, effect)
    return {"schema": "rocket.power.surface.v1", "conclusion": "INDETERMINATE_ASSUMPTIONS_REQUIRED",
            "mom002_state": "NEEDS_PRE_RESULT_GATE_REVIEW", "trials_consumed": 0, "trial_budget": 0,
            "real_outcomes_accessed": False, "draws_per_regime": draws, "bootstrap_draws": bootstrap_draws,
            "seed": 20261005, "bootstrap_seed": 20261002, "numpy_version": np.__version__,
            "geometry": structural_summary(geometry), "results": results,
            "limitations": ["Feature completeness/readiness assumed, not accepted.",
                            "Minimum worthwhile effect and terminal/descriptive economics require human decisions.",
                            "Synthetic features/DGP are assumptions; r is oracle strength, not fitted OOS skill.",
                            "Adversity is conditional on a unit-S Brownian bridge, not verified real paths.",
                            "Cluster bootstrap diagnostics cannot prove stochastic independence."]}
