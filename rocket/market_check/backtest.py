"""Run both backtests and build the report payload."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from rocket.market_check.config import Config
from rocket.market_check.derivatives import simulate_derivatives
from rocket.market_check.episodes import drawdown_warnings, regime_episodes, session_counts
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.portfolio import compare_trade_log, simulate_portfolio
from rocket.market_check.report import ASSUMPTIONS, render_report


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
    portfolio = simulate_portfolio(panel, config)
    derivatives = simulate_derivatives(panel, config)
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
