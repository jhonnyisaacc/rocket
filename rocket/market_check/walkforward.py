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
            "in_sample": performance(
                in_days,
                in_nav,
                rf_daily=_rf_daily(panel, config, in_days),
            ),
            "stitched": performance(chained_days, chained_nav),
        }
    return out


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
