"""Models m1: regularized logistic regression + trivial baselines, stdlib only.

M1: logistic regression, train-only standardization, fixed L2=1,
intercept unpenalized, no tuning. Separate UP/DOWN intercepts, common
feature slopes if counts support it. Deterministic batch gradient
descent with fixed iterations and step size: no randomness anywhere.
B0: expanding-train climatology. B1: single-variable (rv_ratio) logistic.
B2: unfiltered candidate + deterministic every-fourth budget comparator.
B3: seeded block-null matching annual frequency/cooldown (1000 shifts).
"""

from __future__ import annotations

import math
import random

from rocket.momentum import contracts

MODEL_VERSION = contracts.MODEL_VERSION


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def standardize_fit(rows: list[list[float]]) -> tuple[list[float], list[float]]:
    means, sds = [], []
    for j in range(len(rows[0])):
        col = [r[j] for r in rows]
        mu = sum(col) / len(col)
        var = sum((v - mu) ** 2 for v in col) / len(col)
        sd = math.sqrt(var) if var > 0 else 1.0
        means.append(mu)
        sds.append(sd if sd > 0 and math.isfinite(sd) else 1.0)
    return means, sds


def standardize_apply(rows: list[list[float]], means: list[float], sds: list[float]) -> list[list[float]]:
    return [[(v - mu) / sd for v, mu, sd in zip(r, means, sds)] for r in rows]


def fit_logreg(
    X: list[list[float]],
    y: list[int],
    *,
    l2: float = 1.0,
    iters: int = 2000,
    step: float = 0.1,
) -> dict:
    """Batch gradient descent, fixed schedule. Intercept index 0, unpenalized."""
    n = len(X)
    p = len(X[0])
    w = [0.0] * (p + 1)
    for _ in range(iters):
        grad = [0.0] * (p + 1)
        for xi, yi in zip(X, y):
            z = w[0] + sum(w[j + 1] * v for j, v in enumerate(xi))
            err = _sigmoid(z) - yi
            grad[0] += err
            for j, v in enumerate(xi):
                grad[j + 1] += err * v
        w[0] -= step * grad[0] / n
        for j in range(p):
            w[j + 1] -= step * (grad[j + 1] / n + l2 * w[j + 1] / n)
    return {"weights": w, "l2": l2, "iters": iters, "step": step}


def predict_logreg(model: dict, X: list[list[float]]) -> list[float]:
    w = model["weights"]
    return [_sigmoid(w[0] + sum(w[j + 1] * v for j, v in enumerate(xi))) for xi in X]


def design_matrix(rows: list[dict], keys: list[str]) -> tuple[list[list[float]], list[int]]:
    """Rows with any missing key are excluded; exclusion is reported."""
    X, keep = [], []
    for i, r in enumerate(rows):
        vals = [r.get(k) for k in keys]
        if all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals):
            X.append([float(v) for v in vals])  # type: ignore[arg-type]
            keep.append(i)
    return X, keep


def fit_predict_fold(
    train_rows: list[dict],
    test_rows: list[dict],
    keys: list[str],
    target: str = "success",
) -> tuple[list[float], dict]:
    """Fit on train, predict test. Returns (test_probs_aligned, info).

    Test rows with missing features get None (UNKNOWN) and are excluded
    from scoring; info records the exclusion count.
    """
    Xtr, keeptr = design_matrix(train_rows, keys)
    ytr = [int(train_rows[i][target]) for i in keeptr]
    info = {"train_n": len(train_rows), "train_used": len(Xtr), "keys": keys}
    if len(Xtr) < 10 or sum(ytr) == 0 or sum(ytr) == len(ytr):
        return [None] * len(test_rows), {**info, "degenerate": True}
    means, sds = standardize_fit(Xtr)
    model = fit_logreg(standardize_apply(Xtr, means, sds), ytr)
    probs: list[float | None] = []
    for r in test_rows:
        vals = [r.get(k) for k in keys]
        if all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals):
            xs = [(float(v) - mu) / sd for v, mu, sd in zip(vals, means, sds)]  # type: ignore[arg-type]
            probs.append(predict_logreg(model, [xs])[0])
        else:
            probs.append(None)
    return probs, {**info, "means": means, "sds": sds, "weights": model["weights"],
                   "test_missing": sum(p is None for p in probs)}


def climatology(train_rows: list[dict], test_rows: list[dict], target: str = "success") -> list[float]:
    base = sum(int(r[target]) for r in train_rows) / max(len(train_rows), 1)
    return [base] * len(test_rows)


def null_shift_pvalues(
    test_probs: list[float | None],
    test_labels: list[int],
    *,
    annual_count: int,
    seed: int = 7,
    shifts: int = contracts.NULL_SHIFTS,
) -> dict:
    """B3 block-null: circularly shift the score vector (preserves temporal
    clustering) and recompute precision at the same alert budget. Returns
    the null distribution summary and empirical p-value of observed lift."""
    scored = [(p, y) for p, y in zip(test_probs, test_labels) if p is not None]
    if not scored or annual_count <= 0:
        return {"null_n": 0}
    k = max(1, min(annual_count, len(scored)))
    order = sorted(range(len(scored)), key=lambda i: scored[i][0], reverse=True)
    picked = set(order[:k])
    obs = sum(scored[i][1] for i in picked) / k
    rng = random.Random(seed)
    offsets = [rng.randrange(len(scored)) for _ in range(shifts)]
    nulls = []
    for off in offsets:
        rot = scored[off:] + scored[:off]
        top = sorted(range(len(rot)), key=lambda i: rot[i][0], reverse=True)[:k]
        nulls.append(sum(rot[i][1] for i in top) / k)
    nulls.sort()
    pval = (1 + sum(v >= obs for v in nulls)) / (len(nulls) + 1)
    return {"null_n": len(nulls), "null_mean": sum(nulls) / len(nulls),
            "null_p95": nulls[int(0.95 * (len(nulls) - 1))],
            "observed_precision": obs, "empirical_p": pval, "budget_k": k}
