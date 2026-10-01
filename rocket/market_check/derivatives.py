"""Monthly BTC perp and put-overlay backtest. Constant notional, reset each month."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from rocket.market_check.actions import _perps
from rocket.market_check.bs import bs_put
from rocket.market_check.config import Config
from rocket.market_check.mathutil import realized_vol
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.score import score_on, score_path, scoring_days


def _iv(panel: SeriesPanel, config: Config, day: date) -> tuple[float | None, str]:
    view = panel.asof(day, config.lags)
    dvol = view.value("dvol")
    if dvol is not None and dvol > 0:
        return dvol / 100, "black_scholes_dvol"
    realized = realized_vol(view.closes("btc"), config.windows.rv)
    if realized is None or realized <= 0:
        return None, "missing"
    return realized, "black_scholes_realized"


def _rate(panel: SeriesPanel, config: Config, day: date) -> float:
    value = panel.asof(day, config.lags).value("fed_funds")
    if value is None:
        return config.derivatives.fallback_rate
    return value / 100


def _months(days: list[date]) -> list[list[date]]:
    groups: list[list[date]] = []
    current: list[date] = []
    key: tuple[int, int] | None = None
    for day in days:
        stamp = (day.year, day.month)
        if key is None or stamp == key:
            current.append(day)
            key = stamp
            continue
        groups.append(current)
        current = [day]
        key = stamp
    if current:
        groups.append(current)
    return groups


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    active = [row for row in rows if row["success"] is not None]
    pnls = [float(row["pnl"]) for row in active]
    perp_rows = [row for row in rows if row["position"] != "flat"]
    hedge_rows = [row for row in rows if row["hedge"] == "btc_puts" and row["hedge_pnl"] is not None]
    wealth = 1.0
    for pnl in pnls:
        if pnl <= -1:
            wealth = 0.0
            break
        wealth *= 1 + pnl
    def _hit(sample: list[dict[str, Any]], key: str) -> float | None:
        usable = [row for row in sample if row.get(key) is not None]
        if not usable:
            return None
        return sum(1 for row in usable if float(row[key]) > 0) / len(usable)
    return {
        "months": len(rows),
        "active_months": len(active),
        "hit_rate": None if not active else sum(1 for row in active if row["success"]) / len(active),
        "sum_pnl": sum(pnls) if pnls else 0.0,
        "mean_pnl": None if not pnls else sum(pnls) / len(pnls),
        "best_pnl": None if not pnls else max(pnls),
        "worst_pnl": None if not pnls else min(pnls),
        "compounded": wealth - 1 if pnls else 0.0,
        "perp_hit_rate": _hit(perp_rows, "perp_pnl"),
        "hedge_hit_rate": _hit(hedge_rows, "hedge_pnl"),
        "stopped": sum(1 for row in rows if row["stopped"]),
    }


def simulate_derivatives(panel: SeriesPanel, config: Config) -> dict[str, Any]:
    days = [
        day for day in panel.dates("btc")
        if config.window.start <= day <= config.window.end
    ]
    slip = config.costs.perp_slippage_bps / 10_000
    fee = config.costs.perp_fee_bps / 10_000
    path = score_path(panel, scoring_days(panel, config), config)
    rows = []
    for members in _months(days):
        entry_day = members[0]
        entry = panel.asof(entry_day, config.lags).value("btc")
        if entry is None or entry <= 0:
            continue
        scored = score_on(path, entry_day) or score_path(panel, [entry_day], config)[0]
        perps = _perps(scored, config)
        direction = perps["direction"]
        size = float(perps["size"])
        exit_day = members[-1]
        stopped = False
        if direction == "long":
            for day in members[1:]:
                price = panel.asof(day, config.lags).value("btc")
                if price is not None and price <= entry * (1 - config.derivatives.stop):
                    exit_day = day
                    stopped = True
                    break
        elif direction == "short":
            for day in members[1:]:
                price = panel.asof(day, config.lags).value("btc")
                if price is not None and price >= entry * (1 + config.derivatives.stop):
                    exit_day = day
                    stopped = True
                    break
        exit_price = panel.asof(exit_day, config.lags).value("btc") or entry
        hold = [day for day in members if entry_day <= day <= exit_day]
        funding = 0.0
        for day in hold:
            rate = panel.asof(day, config.lags).value("funding_daily") or 0.0
            if direction == "long":
                funding -= size * rate
            elif direction == "short":
                funding += size * rate
        if direction == "long":
            gross = size * ((exit_price * (1 - slip)) / (entry * (1 + slip)) - 1)
            fees = size * fee * 2
        elif direction == "short":
            entry_fill = entry * (1 - slip)
            exit_fill = exit_price * (1 + slip)
            gross = size * (entry_fill - exit_fill) / entry_fill
            fees = size * fee * 2
        else:
            gross = 0.0
            fees = 0.0
        perp_pnl = gross + funding - fees
        hedge = perps["hedge"]
        hedge_pnl = None
        pricing = "none"
        strike = None
        premium = None
        if hedge == "btc_puts":
            iv, pricing = _iv(panel, config, entry_day)
            if iv is None:
                hedge = "none"
                pricing = "missing"
            else:
                strike = entry * (1 - config.derivatives.put_otm)
                years = config.derivatives.put_tenor_days / 365.25
                premium = bs_put(entry, strike, years, iv + config.costs.option_iv_slippage, _rate(panel, config, entry_day))
                remaining_days = (entry_day + timedelta(days=config.derivatives.put_tenor_days) - exit_day).days
                exit_iv, _source = _iv(panel, config, exit_day)
                mark = bs_put(
                    exit_price, strike, max(remaining_days, 0) / 365.25,
                    exit_iv if exit_iv is not None else iv, _rate(panel, config, exit_day),
                )
                option_fees = entry * (config.costs.option_fee_bps_underlying / 10_000) * 2
                # Premium, mark and fees are USD per BTC. P&L is a fraction of the entry spot.
                hedge_pnl = (mark - premium - option_fees) / entry
        total = perp_pnl + (hedge_pnl or 0.0)
        active = direction != "flat" or hedge == "btc_puts"
        rows.append({
            "month": entry_day.strftime("%Y-%m"),
            "date": entry_day.isoformat(),
            "signal": perps["direction"] if direction == "flat" else f"{direction} {size:g}",
            "regime": scored["regime"],
            "position": direction,
            "size": size,
            "entry": entry,
            "exit": exit_price,
            "exit_date": exit_day.isoformat(),
            "stopped": stopped,
            "funding_pnl": funding,
            "fees": fees,
            "perp_pnl": perp_pnl,
            "hedge": hedge,
            "hedge_signal": perps["hedge_signal"],
            "strike": strike,
            "premium": premium,
            "hedge_pnl": hedge_pnl,
            "pricing": pricing,
            "pnl": total,
            "success": (total > 0) if active else None,
            "options": perps["options"],
        })
    oos = config.window.oos_start
    in_rows = [row for row in rows if date.fromisoformat(row["date"]) < oos]
    out_rows = [row for row in rows if date.fromisoformat(row["date"]) >= oos]
    return {
        "rows": rows,
        "full": _summarize(rows),
        "in_sample": _summarize(in_rows),
        "out_of_sample": _summarize(out_rows),
        "pricing_note": (
            "Perps are spot plus historical funding, with fees and slippage. "
            "Puts are Black-Scholes, marked with that day's Deribit DVOL when it exists, "
            "otherwise with trailing realized volatility. They are not Deribit trade prints. "
            "DVOL is a 30-day index used on a 60-day put. Each month is a fresh 1-BTC notional; "
            "the sum of monthly P&L is the primary total, not a compounded equity curve."
        ),
    }
