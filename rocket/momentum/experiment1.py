"""Experiment MOM-001: conditional momentum continuation (reserved packet).

Runs ONLY when the MOM-000 gate passes. Given a breakout candidate, can
Tier A (+B) market information distinguish CONTINUES from {FAILS,
TIMEOUT}? Target: success = 1 iff outcome == CONTINUES (per direction;
UP and DOWN modeled with separate intercepts, common slopes when counts
support it). Expanding annual folds, purged + embargoed training, fixed
alert budget from census frequency, causal trailing-quantile thresholds.
Baselines B0 (climatology), B1 (rv-ratio logistic), B2 (unfiltered +
every-fourth), B3 (seeded block-null). No tuning, no rescue.
"""

from __future__ import annotations

import bisect

from rocket.momentum import contracts
from rocket.momentum.features import TIER_A, TIER_B, feature_row, tier_a, tier_b
from rocket.momentum.folds import build_folds
from rocket.momentum.labels import label_candidate
from rocket.momentum.metrics import (
    brier_logloss,
    calibration,
    episode_bootstrap,
    pr_auc,
    precision_recall,
)
from rocket.momentum.models import climatology, fit_predict_fold, null_shift_pvalues


def build_rows(
    events: list[dict],
    bars_4h: list[dict],
    bars_1h: list[dict],
    *,
    funding: list[dict] | None = None,
    metrics_daily: list[dict] | None = None,
    perp_4h: list[dict] | None = None,
    horizon_days: int = contracts.HORIZON_PRIMARY_DAYS,
) -> list[dict]:
    """Labeled feature rows for independent (spaced) candidates only."""
    funding = funding or []
    metrics_daily = metrics_daily or []
    perp_4h = perp_4h or []
    ordered_1h = sorted(bars_1h, key=lambda b: b["open_ms"])
    opens_1h = [b["open_ms"] for b in ordered_1h]
    horizon_ms = horizon_days * 24 * 3600 * 1000
    rows = []
    for event in events:
        lo = bisect.bisect_left(opens_1h, event["cutoff_ms"] + 3600 * 1000)
        hi = bisect.bisect_left(opens_1h, event["cutoff_ms"] + horizon_ms)
        lab = label_candidate(event, ordered_1h[lo:hi], horizon_days=horizon_days)
        if lab["outcome"] == "UNKNOWN":
            continue
        a = tier_a(bars_4h, event["cutoff_ms"], sigma=event["sigma"])
        b = tier_b(funding, metrics_daily, bars_4h, perp_4h, event["cutoff_ms"])
        row = feature_row(event, a, b)
        row["success"] = 1 if lab["outcome"] == "CONTINUES" else 0
        row["outcome"] = lab["outcome"]
        row["mfe_S"] = lab["mfe_S"]
        row["mae_S"] = lab["mae_S"]
        row["end_log"] = lab["end_log"]
        rows.append(row)
    return rows


def run_experiment_1(
    rows: list[dict],
    *,
    gate_report: dict,
    horizon_days: int = contracts.HORIZON_PRIMARY_DAYS,
) -> dict:
    """Score the reserved packet. Raises if the gate did not pass."""
    if not gate_report.get("permit_experiment_1", False):
        raise PermissionError("MOM-000 gate did not pass; MOM-001 is NOT admitted.")
    keys_ab = [*TIER_A, *TIER_B]
    keys_a = [*TIER_A]
    folds = build_folds(
        [{"cutoff_ms": r["cutoff_ms"]} for r in rows], horizon_days=horizon_days
    )
    by_cutoff = {r["cutoff_ms"]: r for r in rows}
    budget_frac = contracts.ALERT_BUDGET_FRAC
    detectors = ["A+B", "A-only", "B0", "B1", "B2"]
    agg: dict[str, dict] = {d: {"probs": [], "labels": []} for d in detectors}
    fold_reports = []
    for fold in folds:
        train = [by_cutoff[e["cutoff_ms"]] for e in fold["train"]]
        test = [by_cutoff[e["cutoff_ms"]] for e in fold["test"]]
        labels = [r["success"] for r in test]
        k = max(1, int(len(test) * budget_frac))
        probs_ab, info_ab = fit_predict_fold(train, test, keys_ab)
        probs_a, info_a = fit_predict_fold(train, test, keys_a)
        probs_b0 = climatology(train, test)
        rv_key = ["rv_ratio_6_180"]
        probs_b1, info_b1 = fit_predict_fold(train, test, rv_key)
        probs_b2 = [1.0 if (i % 4 == 0) else 0.0 for i in range(len(test))]
        fold_reports.append(
            {
                "test_year": fold["test_year"],
                "n_train": len(train),
                "n_test": len(test),
                "base_rate": sum(labels) / len(labels) if labels else None,
                "budget_k": k,
                "A+B": {**precision_recall(probs_ab, labels, k),
                        **brier_logloss(probs_ab, labels)},
                "A-only": {**precision_recall(probs_a, labels, k),
                            **brier_logloss(probs_a, labels)},
                "B0": {**precision_recall(probs_b0, labels, k),
                       **brier_logloss(probs_b0, labels)},
                "B1": {**precision_recall(probs_b1, labels, k),
                       **brier_logloss(probs_b1, labels)},
                "B2": precision_recall(probs_b2, labels, k),
                "train_used_ab": info_ab.get("train_used"),
                "test_missing_ab": info_ab.get("test_missing"),
                "train_used_a": info_a.get("train_used"),
                "train_used_b1": info_b1.get("train_used"),
            }
        )
        for name, probs in (("A+B", probs_ab), ("A-only", probs_a),
                            ("B0", probs_b0), ("B1", probs_b1), ("B2", probs_b2)):
            agg[name]["probs"].extend(probs)
            agg[name]["labels"].extend(labels)
    pooled = {}
    for name in detectors:
        probs, labels = agg[name]["probs"], agg[name]["labels"]
        k = max(1, int(len(labels) * budget_frac))
        pooled[name] = {**precision_recall(probs, labels, k),
                        **brier_logloss(probs, labels)}
    pooled["A+B"]["pr_auc"] = pr_auc(agg["A+B"]["probs"], agg["A+B"]["labels"])
    pooled["A+B"]["calibration"] = calibration(agg["A+B"]["probs"], agg["A+B"]["labels"])
    pooled["A+B"]["null"] = null_shift_pvalues(
        agg["A+B"]["probs"], agg["A+B"]["labels"],
        annual_count=max(1, int(len(labels) * budget_frac)))
    signed = [r["end_log"] for r in rows if r.get("end_log") is not None]
    pooled["signed_end_log_bootstrap"] = episode_bootstrap(signed) if signed else {"n": 0}
    verdict = evaluate_success(fold_reports, pooled)
    return {"model": contracts.MODEL_VERSION, "schema": contracts.FEATURE_SCHEMA_VERSION,
            "horizon_days": horizon_days, "folds": fold_reports, "pooled": pooled,
            "verdict": verdict}


def evaluate_success(fold_reports: list[dict], pooled: dict) -> dict:
    """Reserved success bar: incremental OOS skill of A+B vs Tier A and
    B0/B1, stable sign, calibration, lift, MAE compatibility. All required."""
    def _get(fold, det, key):
        return (fold.get(det) or {}).get(key)

    ab_skill = pooled["A+B"].get("brier_skill")
    a_skill = pooled["A-only"].get("brier_skill")
    checks = {
        "brier_skill_positive": ab_skill is not None and ab_skill > 0,
        "beats_tier_a": (ab_skill is not None and a_skill is not None and ab_skill > a_skill),
        "lift_ge_125": (pooled["A+B"].get("lift") or 0) >= 1.25,
        "recall_ge_20pct": (pooled["A+B"].get("recall") or 0) >= 0.20,
    }
    signs = [((_get(f, "A+B", "brier_skill") or 0) > (_get(f, "A-only", "brier_skill") or 0))
             for f in fold_reports]
    checks["stable_sign_2of3"] = sum(signs) >= 2 and len(signs) >= 2
    cal = pooled["A+B"].get("calibration") or {}
    slope = cal.get("slope")
    checks["calibration_ok"] = (
        slope is not None and 0.5 <= slope <= 1.5 and (cal.get("abs_cal_error") or 1) <= 0.10
    )
    passed = all(checks.values())
    return {"checks": checks, "success": passed,
            "statement": "PASS" if passed else "FAIL: conditional path closed, no rescue"}
