"""Skill metrics for rare momentum detection. No Sharpe optimization.

Reports precision, lift over base rate, episode recall, PR-AUC, Brier /
log-loss, calibration, direction accuracy conditional on large moves,
false ignition rate, signed forward returns, MFE/MAE, latency, outcome
concentration and detected fraction. Episode bootstrap CIs resample
independent (spaced) candidates only.
"""

from __future__ import annotations

import math
import random


def _safe(values: list[float | None]) -> list[float]:
    return [v for v in values if v is not None and math.isfinite(v)]


def precision_recall(probs: list[float | None], labels: list[int], k: int) -> dict:
    scored = [(p, y) for p, y in zip(probs, labels) if p is not None]
    if not scored or k <= 0:
        return {"k": 0}
    k = min(k, len(scored))
    order = sorted(range(len(scored)), key=lambda i: scored[i][0], reverse=True)
    picked = order[:k]
    tp = sum(scored[i][1] for i in picked)
    base = sum(y for _, y in scored) / len(scored)
    prec = tp / k
    rec = tp / max(sum(y for _, y in scored), 1)
    return {
        "k": k,
        "n_scored": len(scored),
        "precision": prec,
        "base_rate": base,
        "lift": prec / base if base > 0 else None,
        "recall": rec,
        "false_ignition": 1 - prec,
    }


def pr_auc(probs: list[float | None], labels: list[int]) -> float | None:
    scored = sorted(
        ((p, y) for p, y in zip(probs, labels) if p is not None), reverse=True
    )
    if not scored or sum(y for _, y in scored) == 0:
        return None
    total_pos = sum(y for _, y in scored)
    tp = fp = 0
    prev_rec, auc, prev_prec = 0.0, 0.0, 1.0
    for _, y in scored:
        if y:
            tp += 1
        else:
            fp += 1
        prec = tp / (tp + fp)
        rec = tp / total_pos
        auc += (rec - prev_rec) * (prec + prev_prec) / 2
        prev_rec, prev_prec = rec, prec
    return auc


def brier_logloss(probs: list[float | None], labels: list[int]) -> dict:
    scored = [(p, y) for p, y in zip(probs, labels) if p is not None]
    if not scored:
        return {"n": 0}
    brier = sum((p - y) ** 2 for p, y in scored) / len(scored)
    eps = 1e-12
    ll = -sum(y * math.log(min(max(p, eps), 1 - eps)) + (1 - y) * math.log(min(max(1 - p, eps), 1 - eps))
              for p, y in scored) / len(scored)
    base = sum(y for _, y in scored) / len(scored)
    brier_base = base * (1 - base)
    return {"n": len(scored), "brier": brier, "logloss": ll,
            "brier_skill": 1 - brier / brier_base if brier_base > 0 else None}


def calibration(probs: list[float | None], labels: list[int], *, bins: int = 5) -> dict:
    scored = sorted((p, y) for p, y in zip(probs, labels) if p is not None)
    if len(scored) < bins:
        return {"bins": []}
    size = len(scored) // bins
    rows, slope_num, slope_den, ace = [], 0.0, 0.0, 0.0
    mean_p = sum(p for p, _ in scored) / len(scored)
    mean_y = sum(y for _, y in scored) / len(scored)
    for b in range(bins):
        seg = scored[b * size:] if b == bins - 1 else scored[b * size:(b + 1) * size]
        mp = sum(p for p, _ in seg) / len(seg)
        my = sum(y for _, y in seg) / len(seg)
        rows.append({"mean_prob": mp, "empirical": my, "n": len(seg)})
        slope_num += (mp - mean_p) * (my - mean_y)
        slope_den += (mp - mean_p) ** 2
        ace += abs(mp - my) * len(seg) / len(scored)
    return {"bins": rows, "slope": slope_num / slope_den if slope_den > 0 else None,
            "abs_cal_error": ace}


def concentration(weights: list[float]) -> dict:
    """Contribution concentration over positive-MFE weights."""
    pos = sorted((w for w in weights if w and w > 0), reverse=True)
    total = sum(pos)
    if not pos or total <= 0:
        return {"n": 0}
    top1 = pos[0] / total
    top5 = sum(pos[:5]) / total
    cut = total / 2
    run, hhi_n = 0.0, 0
    for w in pos:
        run += w
        hhi_n += 1
        if run >= cut:
            break
    return {"n": len(pos), "top1_share": top1, "top5_share": top5,
            "median_count_for_half": hhi_n}


def episode_bootstrap(
    values: list[float],
    statistic=sum,
    *,
    seed: int = 11,
    reps: int = 2000,
) -> dict:
    """Percentile CI over independent episodes. Statistic over resample."""
    if not values:
        return {"n": 0}
    rng = random.Random(seed)
    n = len(values)
    dist = sorted(statistic([values[rng.randrange(n)] for _ in range(n)]) for _ in range(reps))
    return {"n": n, "mean": sum(values) / n, "lo95": dist[int(0.025 * (reps - 1))],
            "hi95": dist[int(0.975 * (reps - 1))]}
