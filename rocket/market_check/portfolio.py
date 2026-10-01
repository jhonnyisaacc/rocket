"""Porto-style long-only book. Regime sets the cash target; gates allow or block trades."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from rocket.market_check.config import Config
from rocket.market_check.metrics import monthly_returns, performance, slice_path
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.redeploy import redeploy_picks
from rocket.market_check.rules import (
    add_blockers,
    cash_target,
    in_bottom_half,
    plan_trims,
    range_bounds,
    session_return,
    trailing_bounce,
    trim_allowed,
)
from rocket.market_check.score import score_on, score_path, scoring_days


def _price(panel: SeriesPanel, config: Config, day: date, name: str) -> float | None:
    return panel.asof(day, config.lags).value(name)


def _nav(cash: float, shares: dict[str, float], prices: dict[str, float]) -> float:
    return cash + sum(qty * prices[name] for name, qty in shares.items() if name in prices and qty)


def _buy_hold(
    panel: SeriesPanel, config: Config, names: tuple[str, ...], days: list[date],
) -> list[float]:
    slip = config.costs.equity_slippage_bps / 10_000
    start = days[0]
    priced = [(name, _price(panel, config, start, name)) for name in names]
    priced = [(name, price) for name, price in priced if price]
    nav = [1.0]
    if not priced:
        return [1.0 for _ in days]
    weight = 1.0 / len(priced)
    shares = {name: (weight / (price * (1 + slip))) for name, price in priced}
    path = []
    for day in days:
        prices = {}
        for name in shares:
            price = _price(panel, config, day, name)
            if price:
                prices[name] = price
        path.append(_nav(0.0, shares, prices))
    return path or nav


def _rf(panel: SeriesPanel, config: Config, days: list[date]) -> list[float]:
    rates = []
    for day in days[1:]:
        value = panel.asof(day, config.lags).value("fed_funds")
        annual = config.derivatives.fallback_rate if value is None else value / 100
        rates.append(annual / 252)
    return rates


def simulate_portfolio(panel: SeriesPanel, config: Config) -> dict[str, Any]:
    days = [
        day for day in panel.dates("spy")
        if config.window.start <= day <= config.window.end
    ]
    if len(days) < 2:
        raise ValueError("portfolio backtest needs a SPY calendar inside the window")
    slip = config.costs.equity_slippage_bps / 10_000
    start = days[0]
    core_prices = {name: _price(panel, config, start, name) for name in config.portfolio.core}
    available = {name: price for name, price in core_prices.items() if price}
    cash = 1.0
    shares: dict[str, float] = {}
    traded = 0.0
    trades: list[dict[str, Any]] = []
    deploy = 1.0 - config.portfolio.initial_cash
    each = deploy / len(available) if available else 0.0
    for name, price in available.items():
        fill = price * (1 + slip)
        spend = each
        shares[name] = spend / fill
        cash -= spend
        traded += spend
        trades.append({
            "date": start.isoformat(), "ticker": name, "side": "buy",
            "shares": shares[name], "price": fill, "notional": spend, "reason": "initial",
        })
    last_add: dict[str, date] = {}
    redeploy_count = 0
    last_redeploy: date | None = None
    last_bottom: date | None = None
    nav_path = []
    regimes: list[str] = []
    path = score_path(panel, scoring_days(panel, config), config)
    for day in days:
        view = panel.asof(day, config.lags)
        prices = {}
        for name in set(shares) | set(config.portfolio.universe):
            price = view.value(name)
            if price:
                prices[name] = price
        nav = _nav(cash, shares, prices)
        score = score_on(path, day) or {"regime": "unknown", "oil_shock": False, "events_today": []}
        regime = score["regime"]
        bottom = config.model.version == "v3" and bool(score.get("bottom"))
        released = config.model.version == "v3" and bool(score.get("released"))
        if (
            not bottom
            and last_bottom is not None
            and (day - last_bottom).days > config.redeploy.episode_gap_days
        ):
            redeploy_count = 0
            last_bottom = None
        if day != start:
            index_return = session_return(view, "spy")
            index_bounce = trailing_bounce(view, "spy", config.windows.index_bounce_lookback)
            # Hold through the release and for the rest of the open episode, including
            # a day when a fresh spike has not yet printed a new bottom.
            holding = bottom or released or last_bottom is not None
            if holding:
                target = config.redeploy.cash_target
            elif regime != "unknown":
                target = cash_target(regime, index_return, config)
            else:
                target = cash / nav if nav else 0
            if regime != "unknown" and nav > 0:
                allowed: set[str] = set()
                if not holding:
                    for name in config.portfolio.sale_order:
                        if shares.get(name, 0) <= 0 or name not in prices:
                            continue
                        ok, _detail = trim_allowed(
                            name=name,
                            name_return=session_return(view, name),
                            bounce=trailing_bounce(view, name, config.windows.soft_patch),
                            index_return=index_return,
                            index_bounce=index_bounce,
                            regular_hours=config.portfolio.assume_regular_hours,
                            config=config,
                        )
                        if ok:
                            allowed.add(name)
                for name, fraction in plan_trims(shares, prices, cash, nav, target, allowed, config):
                    held = shares[name]
                    qty = held * fraction
                    fill = prices[name] * (1 - slip)
                    proceeds = qty * fill
                    cash += proceeds
                    shares[name] = held - qty
                    traded += proceeds
                    trades.append({
                        "date": day.isoformat(), "ticker": name, "side": "sell",
                        "shares": qty, "price": fill, "notional": proceeds, "reason": "trim_cash_target",
                    })
                nav = _nav(cash, shares, prices)
                if bottom and nav > 0:
                    last_bottom = day
                    gap_ok = last_redeploy is None or (day - last_redeploy).days >= config.redeploy.gap_days
                    room = config.redeploy.tranches - redeploy_count
                    excess = cash - target * nav
                    if gap_ok and room > 0 and excess > config.portfolio.cash_tolerance * nav:
                        picks = redeploy_picks(view, config)
                        if picks:
                            each = (excess / room) / len(picks)
                            bought = False
                            for sleeve, name, price in picks:
                                if each <= 0 or price <= 0 or each > cash:
                                    continue
                                fill = price * (1 + slip)
                                qty = each / fill
                                cash -= each
                                shares[name] = shares.get(name, 0.0) + qty
                                traded += each
                                bought = True
                                trades.append({
                                    "date": day.isoformat(), "ticker": name, "side": "buy",
                                    "shares": qty, "price": fill, "notional": each,
                                    "reason": f"redeploy_{sleeve}",
                                })
                            if bought:
                                redeploy_count += 1
                                last_redeploy = day
                                nav = _nav(cash, shares, prices)
                episode_open = last_bottom is not None and redeploy_count < config.redeploy.tranches
                blockers = add_blockers(
                    regime=regime, oil_shock=bool(score["oil_shock"]), events_today=list(score["events_today"]),
                )
                if (
                    not bottom
                    and not episode_open
                    and not blockers
                    and nav > 0
                    and cash > target * nav + config.portfolio.cash_tolerance * nav
                ):
                    ranked = []
                    for name in config.portfolio.add_names:
                        bounds = range_bounds(view, name, config.windows.range_lookback)
                        price = prices.get(name)
                        if bounds is None or price is None:
                            continue
                        low, high = bounds
                        if not in_bottom_half(price, low, high, config.portfolio.buy_zone_fraction):
                            continue
                        previous = last_add.get(name)
                        if previous is not None and (day - previous).days < config.portfolio.min_days_between_adds:
                            continue
                        midpoint = low + 0.5 * config.portfolio.buy_zone_fraction * (high - low)
                        ranked.append((price / midpoint if midpoint else 999, name, price))
                    if ranked:
                        _depth, name, price = min(ranked)
                        extra = cash - target * nav
                        spend = min(config.portfolio.tranche_nav * nav, extra, cash)
                        if spend > 0 and price > 0:
                            fill = price * (1 + slip)
                            qty = spend / fill
                            cash -= spend
                            shares[name] = shares.get(name, 0.0) + qty
                            traded += spend
                            last_add[name] = day
                            trades.append({
                                "date": day.isoformat(), "ticker": name, "side": "buy",
                                "shares": qty, "price": fill, "notional": spend, "reason": "add_bottom_half",
                            })
                            nav = _nav(cash, shares, prices)
        nav_path.append(nav)
        regimes.append(regime)
    universe = _buy_hold(panel, config, config.portfolio.universe, days)
    spy = _buy_hold(panel, config, ("spy",), days)
    qqq = _buy_hold(panel, config, ("qqq",), days)
    years = max((days[-1] - days[0]).days / 365.25, 1 / 365.25)
    average_nav = sum(nav_path) / len(nav_path)
    turnover = traded / average_nav / years if average_nav else None

    def pack(label: str, start_day: date, end_day: date, *, prior: bool) -> dict[str, Any]:
        cut_days, cut_nav = slice_path(days, nav_path, start_day, end_day, include_prior_base=prior)
        _bdays, bench = slice_path(days, universe, start_day, end_day, include_prior_base=prior)
        _sdays, spy_nav = slice_path(days, spy, start_day, end_day, include_prior_base=prior)
        _qdays, qqq_nav = slice_path(days, qqq, start_day, end_day, include_prior_base=prior)
        cut_rf = _rf(panel, config, cut_days) if len(cut_days) > 1 else []
        return {
            "label": label,
            "strategy": performance(cut_days, cut_nav, rf_daily=cut_rf),
            "equal_weight": performance(cut_days, bench),
            "spy": performance(cut_days, spy_nav),
            "qqq": performance(cut_days, qqq_nav),
            "monthly": {
                "strategy": monthly_returns(cut_days, cut_nav),
                "equal_weight": monthly_returns(cut_days, bench),
                "spy": monthly_returns(cut_days, spy_nav),
            },
        }

    oos = config.window.oos_start
    pre_end = config.window.ondo_live - timedelta(days=1)
    counts: dict[str, int] = {}
    for regime in regimes:
        counts[regime] = counts.get(regime, 0) + 1
    terminal_prices = {
        name: price for name in shares
        if (price := _price(panel, config, days[-1], name))
    }
    terminal_nav = _nav(cash, shares, terminal_prices)
    return {
        "start": days[0].isoformat(),
        "end": days[-1].isoformat(),
        "sessions": len(days),
        "full": pack("full", days[0], days[-1], prior=False),
        "in_sample": pack("in_sample", days[0], oos - timedelta(days=1), prior=False),
        "out_of_sample": pack("out_of_sample", oos, days[-1], prior=True),
        "pre_ondo": pack("pre_ondo", days[0], pre_end, prior=False),
        "post_ondo": pack("post_ondo", config.window.ondo_live, days[-1], prior=True),
        "turnover_annual": turnover,
        "traded_notional": traded,
        "trade_count": len(trades),
        "trades_by_name": _trade_counts(trades),
        "trades": trades,
        "regime_sessions": counts,
        "terminal_cash_weight": cash / terminal_nav if terminal_nav else None,
        "ondo_live": config.window.ondo_live.isoformat(),
        "proxy_note": (
            "Sessions before the Ondo live date are marked as a 1:1 underlying proxy. "
            "The same slippage is charged the whole way; the split is reported separately."
        ),
        "nav": [{"date": day.isoformat(), "nav": value, "regime": regime} for day, value, regime in zip(days, nav_path, regimes, strict=True)],
    }


def _trade_counts(trades: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for trade in trades:
        bucket = counts.setdefault(trade["ticker"], {"buy": 0, "sell": 0})
        bucket[trade["side"]] = bucket.get(trade["side"], 0) + 1
    return counts


def compare_trade_log(logged: list[dict[str, Any]], simulated: list[dict[str, Any]], *, window_days: int = 5) -> list[dict[str, Any]]:
    """Match a caller trade log to simulated trades. This does not invent a cost basis.

    A same-week fill is `matched`. A sell whose simulated position was already flat
    is `already_exited`: the model agrees with the exit and records when it happened.
    """
    ordered = sorted(simulated, key=lambda trade: trade["date"])
    rows = []
    for item in logged:
        stamp = item["date"] if isinstance(item["date"], date) else date.fromisoformat(str(item["date"])[:10])
        ticker = item["ticker"]
        side = item["side"]
        hits = []
        for trade in ordered:
            if trade["ticker"] != ticker or trade["side"] != side:
                continue
            traded = date.fromisoformat(trade["date"])
            if abs((traded - stamp).days) <= window_days:
                hits.append(trade["date"])
        balance = 0.0
        last_same_side = None
        for trade in ordered:
            traded = date.fromisoformat(trade["date"])
            if traded > stamp or trade["ticker"] != ticker:
                continue
            if trade["side"] == "buy":
                balance += float(trade["shares"])
            elif trade["side"] == "sell":
                balance -= float(trade["shares"])
                if trade["side"] == side:
                    last_same_side = traded
        status = "unmatched"
        explanation = "No simulated fill within the window, and the simulated book was not already flat."
        if hits:
            status = "matched"
            explanation = "Simulated fill within the match window."
        elif side == "sell" and last_same_side is not None and balance <= 1e-8:
            status = "already_exited"
            gap = (stamp - last_same_side).days
            explanation = (
                f"Simulated position was already flat. Last simulated sell was {last_same_side.isoformat()}, "
                f"{gap} days earlier. The model sells this name on strength before the logged date, "
                "so the log is the same exit, not a same-week fill."
            )
        rows.append({
            "date": stamp.isoformat(),
            "ticker": ticker,
            "side": side,
            "note": item.get("note") or "",
            "simulated_dates": hits,
            "matched": status == "matched",
            "recognized": status in {"matched", "already_exited"},
            "status": status,
            "last_simulated": last_same_side.isoformat() if last_same_side and status == "already_exited" else None,
            "days_apart": (stamp - last_same_side).days if last_same_side and status == "already_exited" else None,
            "explanation": explanation,
        })
    return rows
