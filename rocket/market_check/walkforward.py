"""Walk-forward evaluation for fixed market-check rules.

No fitting happens here: the rule set is fixed, so walk-forward is a
robustness lens, not a tuner. One honest run covers the tuning universe
(2024-10-01 to 2026-05-31); its NAV path is sliced into test segments and
restitched. The holdout (2026-06-01 to 2026-09-30) is never touched by this
module: see scripts that evaluate it exactly once at the very end.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from typing import Any

from rocket.market_check.config import Config
from rocket.market_check.metrics import performance
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.portfolio import _buy_hold, simulate_portfolio

# Tuning universe: everything a variant choice may look at. The holdout
# starts the next day and is evaluated exactly once, at the very end.
TUNE_START = date(2024, 10, 1)
TUNE_END = date(2026, 5, 31)
HOLDOUT_START = date(2026, 6, 1)
IN_SAMPLE_END = date(2025, 9, 30)

# Logged walk-forward runs behind the frozen rule. Feeds the deflated Sharpe.
N_TRIALS = 43

Variant = Callable[[Config], Config]


def tune_config(base: Config, variant: Variant | None = None) -> Config:
    """Window the base config to the tuning universe, optionally varied."""
    config = replace(
        base,
        window=replace(base.window, start=TUNE_START, end=TUNE_END),
    )
    return variant(config) if variant is not None else config


def run_variant(
    panel: SeriesPanel,
    base: Config,
    variant: Variant | None = None,
) -> dict[str, Any]:
    """One honest run of a variant over the tuning universe."""
    from rocket.market_check.derivatives import simulate_derivatives

    config = tune_config(base, variant)
    book = simulate_portfolio(panel, config)
    derivs = simulate_derivatives(panel, config)
    return {"config": config, "book": book, "derivatives": derivs}


def _slice_nav(
    nav: list[dict[str, Any]],
    start: date,
    end: date,
) -> list[tuple[date, float]]:
    rows = [
        (date.fromisoformat(row["date"]), float(row["nav"]))
        for row in nav
        if start <= date.fromisoformat(row["date"]) <= end
    ]
    return rows


def test_segments() -> list[tuple[str, date, date]]:
    """Calendar quarters covering the tuning universe (stitched = universe)."""
    return [
        ("2024-Q4", date(2024, 10, 1), date(2024, 12, 31)),
        ("2025-Q1", date(2025, 1, 1), date(2025, 3, 31)),
        ("2025-Q2", date(2025, 4, 1), date(2025, 6, 30)),
        ("2025-Q3", date(2025, 7, 1), date(2025, 9, 30)),
        ("2025-Q4", date(2025, 10, 1), date(2025, 12, 31)),
        ("2026-Q1", date(2026, 1, 1), date(2026, 3, 31)),
        ("2026-Q2-", date(2026, 4, 1), date(2026, 5, 31)),
    ]


def _rf_daily(panel: SeriesPanel, config: Config, days: list[date]) -> list[float]:
    rates = []
    for day in days[1:]:
        value = panel.asof(day, config.lags).value("fed_funds")
        annual = config.derivatives.fallback_rate if value is None else value / 100
        rates.append(annual / 252)
    return rates


def summarize(
    panel: SeriesPanel,
    base: Config,
    result: dict[str, Any],
) -> dict[str, Any]:
    """In-sample stats plus per-segment stats plus the stitched headline.

    The stitched curve chains each test segment's relative returns from 1.0,
    so the headline is the out-of-sample segment path, not the continuous
    run. Sharpe matches the report convention (risk-free-adjusted).
    """
    book = result["book"]
    config = result["config"]
    nav = book["nav"]
    segments = []
    seg_rows: list[tuple[date, float]] = []
    for label, start, end in test_segments():
        rows = _slice_nav(nav, start, end)
        if len(rows) < 2:
            continue
        seg_days = [day for day, _ in rows]
        seg_nav = [value for _, value in rows]
        stats = performance(
            seg_days,
            seg_nav,
            rf_daily=_rf_daily(panel, config, seg_days),
        )
        segments.append({"segment": label, **stats})
        seg_rows.extend(rows)
    seg_rows.sort()
    chained_days, chained_nav = _chain(seg_rows)
    # Report convention: the strategy Sharpe is risk-free-adjusted.
    stitched = (
        performance(
            chained_days,
            chained_nav,
            rf_daily=_rf_daily(panel, config, chained_days),
        )
        if len(chained_days) > 1
        else {
            "cagr": None,
            "max_drawdown": None,
            "volatility": None,
            "sharpe": None,
            "total_return": None,
        }
    )
    in_rows = _slice_nav(nav, TUNE_START, IN_SAMPLE_END)
    in_days = [day for day, _ in in_rows]
    in_nav = [value for _, value in in_rows]
    in_sample = performance(
        in_days,
        in_nav,
        rf_daily=_rf_daily(panel, config, in_days),
    )
    return {
        "in_sample": in_sample,
        "stitched": stitched,
        "segments": segments,
        "trades": book["trade_count"],
        "turnover": book["turnover_annual"],
    }


def _chain(rows: list[tuple[date, float]]) -> tuple[list[date], list[float]]:
    """Chain relative returns from 1.0 over non-contiguous segment slices."""
    days: list[date] = []
    nav: list[float] = [1.0]
    started = False
    for day, prev, nxt in [(rows[i][0], rows[i - 1][1], rows[i][1]) for i in range(1, len(rows))]:
        if not started:
            days.append(rows[0][0])
            started = True
        days.append(day)
        nav.append(nav[-1] * (nxt / prev if prev else 1.0))
    return days, nav


def benchmark_curves(
    panel: SeriesPanel,
    base: Config,
) -> dict[str, dict[str, Any]]:
    """Buy-and-hold curves over the tuning universe. No free parameters:
    computed once and reused for every variant."""
    config = tune_config(base)
    days = [day for day in panel.dates("spy") if TUNE_START <= day <= TUNE_END]
    out = {}
    for label, names in (
        ("equal_weight", config.portfolio.universe),
        ("spy", ("spy",)),
        ("qqq", ("qqq",)),
    ):
        path = _buy_hold(panel, config, names, days)
        rows = [(day, value) for day, value in zip(days, path, strict=True)]
        in_rows = [(day, value) for day, value in rows if day <= IN_SAMPLE_END]
        seg_rows = []
        for _label, start, end in test_segments():
            seg_rows.extend((day, value) for day, value in rows if start <= day <= end)
        seg_rows.sort()
        chained_days, chained_nav = _chain(seg_rows)
        in_days = [day for day, _ in in_rows]
        in_nav = [value for _, value in in_rows]
        out[label] = {
            # Report convention is raw Sharpe for benchmarks; stitched_rf is
            # the like-for-like comparator for the (rf-adjusted) strategy.
            "in_sample": performance(
                in_days,
                in_nav,
                rf_daily=_rf_daily(panel, config, in_days),
            ),
            "stitched": performance(chained_days, chained_nav),
            "stitched_rf": performance(
                chained_days,
                chained_nav,
                rf_daily=_rf_daily(panel, config, chained_days),
            ),
        }
    return out


def holdout_summary(
    panel: SeriesPanel,
    base: Config,
    full_book: dict[str, Any],
) -> dict[str, Any]:
    """The single holdout evaluation: strategy vs benchmarks sliced from one
    full-window run of the frozen rule. No selection may use these numbers."""
    end = base.window.end
    rows = _slice_nav(full_book["nav"], HOLDOUT_START, end)
    days = [day for day, _ in rows]
    nav = [value for _, value in rows]
    strategy = performance(
        days,
        nav,
        rf_daily=_rf_daily(panel, base, days),
    )
    out = {"strategy": strategy}
    curves = _buy_hold_many(panel, base, days)
    rf = _rf_daily(panel, base, days)
    for label, path in curves.items():
        out[label] = performance(days, path)
        out[f"{label}_rf"] = performance(days, path, rf_daily=rf)
    return {"start": HOLDOUT_START.isoformat(), "end": end.isoformat(), **out}


def _buy_hold_many(
    panel: SeriesPanel,
    base: Config,
    days: list[date],
) -> dict[str, list[float]]:
    config = replace(
        base,
        window=replace(base.window, start=days[0], end=days[-1]),
    )
    return {
        "equal_weight": _buy_hold(panel, config, config.portfolio.universe, days),
        "spy": _buy_hold(panel, config, ("spy",), days),
        "qqq": _buy_hold(panel, config, ("qqq",), days),
    }


def sensitivity_cells() -> list[tuple[str, str, float]]:
    """(label, field, value): +-20% around each of the six tuned v6 params."""
    return [
        ("gate 10%", "gate", 0.10),
        ("gate 14%", "gate", 0.14),
        ("credit 40bp", "cred", 0.40),
        ("credit 60bp", "cred", 0.60),
        ("hold 25%", "hold", 0.25),
        ("hold 35%", "hold", 0.35),
        ("VIX combo 20", "vixc", 20.0),
        ("VIX combo 30", "vixc", 30.0),
        ("stop 12%", "stop", 0.12),
        ("stop 18%", "stop", 0.18),
        ("take 24%", "take", 0.24),
        ("take 36%", "take", 0.36),
    ]


def apply_cell(base: Config, field: str, value: float) -> Config:
    """One sensitivity perturbation of the frozen v6 rule."""
    if field == "gate":
        return replace(base, redeploy=replace(base.redeploy, spy_drawdown=value))
    if field == "cred":
        return replace(base, model=replace(base.model, v6_credit_widen=value))
    if field == "hold":
        return replace(base, model=replace(base.model, v6_hold_cash=value))
    if field == "vixc":
        stress = replace(base.regime.stress, vix_level_caution=value)
        return replace(base, regime=replace(base.regime, stress=stress))
    if field == "stop":
        return replace(base, model=replace(base.model, v6_stop=value))
    if field == "take":
        return replace(base, model=replace(base.model, v6_take=value))
    raise ValueError(f"unknown sensitivity field {field}")


def run_sensitivity(
    panel: SeriesPanel,
    base: Config,
) -> list[dict[str, Any]]:
    """IS and stitched Sharpe/DD for each sensitivity cell (stocks leg)."""
    rows = []
    for label, field, value in sensitivity_cells():
        result = run_variant(panel, base, lambda cfg, f=field, v=value: apply_cell(cfg, f, v))
        summary = summarize(panel, base, result)
        rows.append(
            {
                "cell": label,
                "is_sharpe": summary["in_sample"]["sharpe"],
                "is_dd": summary["in_sample"]["max_drawdown"],
                "stitched_sharpe": summary["stitched"]["sharpe"],
                "stitched_dd": summary["stitched"]["max_drawdown"],
                "trades": summary["trades"],
            }
        )
    return rows


def summarize_no_april(
    panel: SeriesPanel,
    base: Config,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Stitched stats with April 2025 (the crash + rebound month) excised."""
    book = result["book"]
    rows = [
        (date.fromisoformat(row["date"]), float(row["nav"]))
        for row in book["nav"]
        if not (row["date"] >= "2025-04-01" and row["date"] <= "2025-04-30")
    ]
    days = [day for day, _ in rows]
    nav = [value for _, value in rows]
    kept = performance(days, nav)
    return {"stitched_no_april_2025": kept}
