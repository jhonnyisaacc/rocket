"""Run both backtests and build the report payload."""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from rocket.market_check.config import Config
from rocket.market_check.derivatives import simulate_derivatives
from rocket.market_check.diagnosis import diagnose, entry_quality
from rocket.market_check.episodes import drawdown_warnings, regime_episodes, session_counts
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.portfolio import compare_trade_log, simulate_portfolio
from rocket.market_check.report import ASSUMPTIONS, render_report


def _as_version(config: Config, version: str) -> Config:
    return replace(config, model=replace(config.model, version=version))


def _v4_config(config: Config, caution: str, puts: bool) -> Config:
    return replace(
        config,
        model=replace(config.model, version="v4", v4_caution=caution, v4_puts=puts),
    )


def _sharpe(book: dict[str, Any]) -> float:
    value = book["in_sample"]["strategy"].get("sharpe")
    return float(value) if isinstance(value, (int, float)) else float("-inf")


def _v4_race(panel: SeriesPanel, config: Config) -> dict[str, Any]:
    """Pick the caution level and the put switch on in-sample numbers only.

    Out-of-sample paths are not read here. A tie keeps the normal 35-45% band
    and drops the puts.
    """
    band = simulate_portfolio(panel, _v4_config(config, "band", False))
    light = simulate_portfolio(panel, _v4_config(config, "light", False))
    caution = "light" if _sharpe(light) > _sharpe(band) else "band"
    book = light if caution == "light" else band
    with_puts = simulate_derivatives(panel, _v4_config(config, caution, True))
    without = simulate_derivatives(panel, _v4_config(config, caution, False))
    puts = float(with_puts["in_sample"]["sum_pnl"]) > float(without["in_sample"]["sum_pnl"])
    return {
        "caution": caution,
        "puts": puts,
        "book": book,
        "derivs": with_puts if puts else without,
        "band_sharpe": band["in_sample"]["strategy"].get("sharpe"),
        "light_sharpe": light["in_sample"]["strategy"].get("sharpe"),
        "band_cagr": band["in_sample"]["strategy"].get("cagr"),
        "light_cagr": light["in_sample"]["strategy"].get("cagr"),
        "band_dd": band["in_sample"]["strategy"].get("max_drawdown"),
        "light_dd": light["in_sample"]["strategy"].get("max_drawdown"),
        "puts_pnl": with_puts["in_sample"]["sum_pnl"],
        "no_puts_pnl": without["in_sample"]["sum_pnl"],
        "puts_only": with_puts["in_sample"].get("put_pnl"),
        "long_pnl": without["in_sample"].get("perp_pnl"),
    }


def _headline(portfolio: dict[str, Any], derivatives: dict[str, Any]) -> dict[str, Any]:
    def side(block: dict[str, Any]) -> dict[str, Any]:
        return {
            "strategy": block["strategy"],
            "equal_weight": block["equal_weight"],
            "spy": block["spy"],
        }
    return {
        "regime_sessions": portfolio["regime_sessions"],
        "full": side(portfolio["full"]),
        "in_sample": side(portfolio["in_sample"]),
        "out_of_sample": side(portfolio["out_of_sample"]),
        "derivatives": {
            "full": derivatives["full"],
            "in_sample": derivatives["in_sample"],
            "out_of_sample": derivatives["out_of_sample"],
        },
    }


def _robustness_record(
    panel: SeriesPanel, config: Config, portfolio: dict[str, Any],
) -> dict[str, Any]:
    """Walk-forward summary, holdout slice, sensitivity grid, and deflated
    Sharpe for the live rule. Deterministic from (panel, config): the
    holdout slice is the single sanctioned evaluation of frozen rules —
    no variant was selected on it (see EXPERIMENTS.md)."""
    from rocket.market_check import walkforward as wf
    from rocket.market_check.metrics import deflated_sharpe

    tuned = wf.run_variant(panel, config, None)
    summary = wf.summarize(panel, config, tuned)
    no_april = wf.summarize_no_april(panel, config, tuned)
    benchmarks = wf.benchmark_curves(panel, config)
    nav = [(row["date"], row["nav"]) for row in tuned["book"]["nav"]]
    stitched_rets = [b[1] / a[1] - 1 for a, b in zip(nav[:-1], nav[1:]) if a[1]]
    dsr = deflated_sharpe(summary["stitched"]["sharpe"] or 0.0, stitched_rets, wf.N_TRIALS)
    return {
        "tune_start": wf.TUNE_START.isoformat(),
        "tune_end": wf.TUNE_END.isoformat(),
        "holdout": wf.holdout_summary(panel, config, portfolio),
        "in_sample": summary["in_sample"],
        "stitched": summary["stitched"],
        "segments": summary["segments"],
        "no_april": no_april["stitched_no_april_2025"],
        "benchmarks": benchmarks,
        "sensitivity": wf.run_sensitivity(panel, config),
        "deflated_sharpe": dsr,
        "trials": wf.N_TRIALS,
        "trades": summary["trades"],
        "turnover": summary["turnover"],
    }


def load_trade_log(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            if not raw.get("date") or not raw.get("ticker") or not raw.get("side"):
                raise ValueError("trade log needs date, ticker and side columns")
            rows.append({
                "date": date.fromisoformat(str(raw["date"])[:10]),
                "ticker": str(raw["ticker"]).upper(),
                "side": str(raw["side"]).lower(),
                "note": raw.get("note") or "",
            })
    return rows


def run_backtest(
    panel: SeriesPanel,
    config: Config,
    *,
    trade_log: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    race = _v4_race(panel, config)
    if config.model.v4_caution != race["caution"] or config.model.v4_puts != race["puts"]:
        raise ValueError(
            "v4 config is "
            f"{config.model.v4_caution} with puts {config.model.v4_puts}; "
            f"the in-sample choice is {race['caution']} with puts {race['puts']}"
        )
    if config.model.version == "v4":
        portfolio, derivatives = race["book"], race["derivs"]
    else:
        portfolio = simulate_portfolio(panel, config)
        derivatives = simulate_derivatives(panel, config)
    ran = {
        config.model.version: (portfolio, derivatives),
        "v4": (race["book"], race["derivs"]),
    }
    for version in ("v1", "v2", "v3"):
        if version in ran:
            continue
        alt = _as_version(config, version)
        ran[version] = (simulate_portfolio(panel, alt), simulate_derivatives(panel, alt))
    comparison = {}
    for version, (book, derivs) in ran.items():
        comparison[version] = _headline(book, derivs)
        comparison[version]["entries"] = entry_quality(panel, config, book["trades"], derivs["rows"])
    logged = [
        {"date": item.date, "ticker": item.ticker, "side": item.side, "note": item.note}
        for item in config.current_book.trades
    ]
    if trade_log:
        logged.extend(trade_log)
    book = config.current_book
    result = {
        "portfolio": portfolio,
        "derivatives": derivatives,
        "assumptions": list(ASSUMPTIONS),
        "robustness": _robustness_record(panel, config, portfolio),
        "oos_start": config.window.oos_start.isoformat(),
        "trade_log": compare_trade_log(logged, portfolio["trades"]),
        "current_book": {
            "as_of": book.as_of.isoformat(),
            "nav_usd": book.nav_usd,
            "weights": book.weights,
            "note": book.note,
        },
        "meta": {
            "series_count": len(panel.names()),
            "sources": panel.meta.get("sources") or {},
        },
        "execution_enabled": False,
        "model_version": config.model.version,
        "comparison": comparison,
        "v4_selection": {
            key: value for key, value in race.items() if key not in {"book", "derivs"}
        },
        "diagnosis": diagnose(panel, config),
        "stress_record": {
            "episodes": regime_episodes(portfolio["nav"], config.window.oos_start),
            "sessions": session_counts(portfolio["nav"], config.window.oos_start),
            "drawdowns": drawdown_warnings(panel, config, portfolio["nav"]),
            "note": (
                "Stress cuts were checked on the in-sample half only. "
                "Out-of-sample episodes are reported with the same cuts."
            ),
        },
    }
    result["markdown"] = render_report(result)
    return result
