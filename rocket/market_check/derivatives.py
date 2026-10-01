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


def _put_pnl(
    panel: SeriesPanel, config: Config, entry_day: date, exit_day: date, entry_spot: float,
) -> tuple[float, str, float | None, float | None]:
    iv, pricing = _iv(panel, config, entry_day)
    if iv is None or entry_spot <= 0:
        return 0.0, "missing", None, None
    strike = entry_spot * (1 - config.derivatives.put_otm)
    years = config.derivatives.put_tenor_days / 365.25
    premium = bs_put(
        entry_spot, strike, years, iv + config.costs.option_iv_slippage, _rate(panel, config, entry_day),
    )
    exit_spot = panel.asof(exit_day, config.lags).value("btc") or entry_spot
    remaining = (entry_day + timedelta(days=config.derivatives.put_tenor_days) - exit_day).days
    exit_iv, _source = _iv(panel, config, exit_day)
    mark = bs_put(
        exit_spot, strike, max(remaining, 0) / 365.25,
        exit_iv if exit_iv is not None else iv, _rate(panel, config, exit_day),
    )
    option_fees = entry_spot * (config.costs.option_fee_bps_underlying / 10_000) * 2
    return (mark - premium - option_fees) / entry_spot, pricing, strike, premium


def _warning(previous: dict[str, Any] | None, today: dict[str, Any] | None) -> bool:
    if today is None:
        return False
    now = today["regime"]
    before = previous["regime"] if previous else "neutral"
    if now == "risk-off" and before != "risk-off":
        return True
    return now == "caution" and before not in {"caution", "risk-off"}


def _btc_drawdown(panel: SeriesPanel, config: Config, day: date) -> float | None:
    closes = panel.asof(day, config.lags).closes("btc", config.redeploy.peak_lookback)
    if len(closes) < 20:
        return None
    peak = max(closes)
    if peak <= 0:
        return None
    return closes[-1] / peak - 1


def _simulate_timed(panel: SeriesPanel, config: Config) -> dict[str, Any]:
    """v3: puts on a fresh warning, longs only on the buy-the-low signal. No monthly drift bet."""
    days = [
        day for day in panel.dates("spy")
        if config.window.start <= day <= config.window.end
    ]
    slip = config.costs.perp_slippage_bps / 10_000
    fee = config.costs.perp_fee_bps / 10_000
    path = score_path(panel, scoring_days(panel, config), config)
    rows = []
    for members in _months(days):
        put_entry: date | None = None
        put_exit: date | None = None
        long_entry: date | None = None
        long_exit: date | None = None
        stopped = False
        for index, day in enumerate(members):
            scored = score_on(path, day)
            previous = score_on(path, members[index - 1]) if index else score_on(
                path, day - timedelta(days=1),
            )
            if put_entry is None and _warning(previous, scored):
                put_entry = day
                put_exit = members[-1]
            if (
                put_entry is not None
                and put_exit == members[-1]
                and scored
                and scored.get("bottom")
                and day >= put_entry
            ):
                put_exit = day
            if long_entry is None and scored and scored.get("bottom"):
                drawdown = _btc_drawdown(panel, config, day)
                if drawdown is not None and drawdown <= -config.redeploy.btc_drawdown:
                    long_entry = day
                    long_exit = day
            elif long_entry is not None and long_exit == long_entry and day > long_entry:
                held = [item for item in members if long_entry <= item <= day]
                price = panel.asof(day, config.lags).value("btc")
                entry_spot = panel.asof(long_entry, config.lags).value("btc") or price
                if price is not None and entry_spot and price <= entry_spot * (1 - config.derivatives.stop):
                    long_exit = day
                    stopped = True
                elif len(held) > config.redeploy.hold_sessions:
                    long_exit = day
        if long_entry is not None and long_exit == long_entry:
            long_exit = members[-1]
        if put_entry is not None and put_exit is not None and put_exit < put_entry:
            put_exit = put_entry
        direction = "long" if long_entry else "flat"
        size = config.derivatives.long_size if long_entry else 0.0
        hedge = "btc_puts" if put_entry else "none"
        perp_pnl = 0.0
        funding = 0.0
        fees = 0.0
        entry_price = panel.asof(members[0], config.lags).value("btc") or 0.0
        exit_price = panel.asof(members[-1], config.lags).value("btc") or entry_price
        if long_entry and long_exit:
            entry_price = panel.asof(long_entry, config.lags).value("btc") or entry_price
            exit_price = panel.asof(long_exit, config.lags).value("btc") or exit_price
            hold = [day for day in members if long_entry <= day <= long_exit]
            for day in hold:
                rate = panel.asof(day, config.lags).value("funding_daily") or 0.0
                funding -= size * rate
            gross = size * ((exit_price * (1 - slip)) / (entry_price * (1 + slip)) - 1) if entry_price else 0.0
            fees = size * fee * 2
            perp_pnl = gross + funding - fees
        hedge_pnl = None
        pricing = "none"
        strike = None
        premium = None
        if put_entry and put_exit:
            spot = panel.asof(put_entry, config.lags).value("btc") or entry_price
            hedge_pnl, pricing, strike, premium = _put_pnl(panel, config, put_entry, put_exit, spot)
            if pricing == "missing":
                hedge = "none"
                hedge_pnl = None
            if direction == "flat":
                entry_price = spot
                exit_price = panel.asof(put_exit, config.lags).value("btc") or spot
        parts = []
        if put_entry and hedge == "btc_puts":
            parts.append("warning put")
        if long_entry:
            parts.append("bottom long")
        signal = " + ".join(parts) if parts else "flat"
        total = perp_pnl + (hedge_pnl or 0.0)
        active = long_entry is not None or hedge == "btc_puts"
        regime = "neutral"
        anchor = long_entry or put_entry or members[0]
        scored = score_on(path, anchor)
        if scored:
            regime = scored["regime"]
        rows.append({
            "month": members[0].strftime("%Y-%m"),
            "date": (long_entry or put_entry or members[0]).isoformat(),
            "signal": signal,
            "regime": regime,
            "position": direction,
            "size": size,
            "entry": entry_price,
            "exit": exit_price,
            "exit_date": (long_exit or put_exit or members[-1]).isoformat(),
            "stopped": stopped,
            "funding_pnl": funding,
            "fees": fees,
            "perp_pnl": perp_pnl,
            "hedge": hedge,
            "hedge_signal": hedge == "btc_puts",
            "strike": strike,
            "premium": premium,
            "hedge_pnl": hedge_pnl,
            "pricing": pricing,
            "pnl": total,
            "success": (total > 0) if active else None,
            "options": "n/a",
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
            "v3 drops the monthly long/short bet. A put is opened only when the regime steps up "
            "into caution or risk-off, and it is marked through the buy-the-low day or month-end. "
            "A long is opened only on the buy-the-low signal while BTC is still in a drawdown, "
            "with the same stop, and held for the configured number of sessions or to month-end. "
            "Puts are Black-Scholes on Deribit DVOL when that print exists, otherwise realized vol. "
            "Each expression is still scaled as a fraction of one BTC."
        ),
    }


def simulate_derivatives(panel: SeriesPanel, config: Config) -> dict[str, Any]:
    if config.model.version == "v3":
        return _simulate_timed(panel, config)
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
