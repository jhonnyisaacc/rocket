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
    hedge_rows = [
        row for row in rows if row["hedge"] == "btc_puts" and row["hedge_pnl"] is not None
    ]
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
        "hit_rate": None
        if not active
        else sum(1 for row in active if row["success"]) / len(active),
        "sum_pnl": sum(pnls) if pnls else 0.0,
        "mean_pnl": None if not pnls else sum(pnls) / len(pnls),
        "best_pnl": None if not pnls else max(pnls),
        "worst_pnl": None if not pnls else min(pnls),
        "compounded": wealth - 1 if pnls else 0.0,
        "perp_hit_rate": _hit(perp_rows, "perp_pnl"),
        "hedge_hit_rate": _hit(hedge_rows, "hedge_pnl"),
        "perp_pnl": sum(float(row["perp_pnl"]) for row in rows),
        "put_pnl": sum(float(row["hedge_pnl"]) for row in rows if row.get("hedge_pnl") is not None),
        "stopped": sum(1 for row in rows if row["stopped"]),
    }


def _put_pnl(
    panel: SeriesPanel,
    config: Config,
    entry_day: date,
    exit_day: date,
    entry_spot: float,
) -> tuple[float, str, float | None, float | None]:
    iv, pricing = _iv(panel, config, entry_day)
    if iv is None or entry_spot <= 0:
        return 0.0, "missing", None, None
    strike = entry_spot * (1 - config.derivatives.put_otm)
    years = config.derivatives.put_tenor_days / 365.25
    premium = bs_put(
        entry_spot,
        strike,
        years,
        iv + config.costs.option_iv_slippage,
        _rate(panel, config, entry_day),
    )
    exit_spot = panel.asof(exit_day, config.lags).value("btc") or entry_spot
    remaining = (entry_day + timedelta(days=config.derivatives.put_tenor_days) - exit_day).days
    exit_iv, _source = _iv(panel, config, exit_day)
    mark = bs_put(
        exit_spot,
        strike,
        max(remaining, 0) / 365.25,
        exit_iv if exit_iv is not None else iv,
        _rate(panel, config, exit_day),
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
    days = [day for day in panel.dates("spy") if config.window.start <= day <= config.window.end]
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
            previous = (
                score_on(path, members[index - 1])
                if index
                else score_on(
                    path,
                    day - timedelta(days=1),
                )
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
                if (
                    price is not None
                    and entry_spot
                    and price <= entry_spot * (1 - config.derivatives.stop)
                ):
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
            gross = (
                size * ((exit_price * (1 - slip)) / (entry_price * (1 + slip)) - 1)
                if entry_price
                else 0.0
            )
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
        rows.append(
            {
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
            }
        )
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


def _price_on(panel: SeriesPanel, config: Config, day: date) -> float | None:
    return panel.asof(day, config.lags).value("btc")


def _long_slice(
    panel: SeriesPanel,
    config: Config,
    days: list[date],
    entry: date,
    exit_day: date,
    month: list[date],
    size: float,
    slip: float,
    fee: float,
) -> float:
    """Mark-to-market of one long inside this month. Costs land on the real entry and exit."""
    held = [day for day in month if entry <= day <= exit_day]
    if not held:
        return 0.0
    first, last = held[0], held[-1]
    if first == entry:
        start_price = _price_on(panel, config, entry) or 0.0
        entry_slip = slip
    else:
        previous = days[days.index(first) - 1]
        start_price = _price_on(panel, config, previous) or 0.0
        entry_slip = 0.0
    end_price = _price_on(panel, config, last) or start_price
    exit_slip = slip if last == exit_day else 0.0
    gross = 0.0
    if start_price:
        gross = size * ((end_price * (1 - exit_slip)) / (start_price * (1 + entry_slip)) - 1)
    funding = 0.0
    for day in held:
        funding -= size * (panel.asof(day, config.lags).value("funding_daily") or 0.0)
    fees = size * fee * ((first == entry) + (last == exit_day))
    return gross + funding - fees


def _next_session(days: list[date], day: date) -> date | None:
    """Fill session after a decision day. None when no later session exists."""
    index = {item: position for position, item in enumerate(days)}.get(day)
    if index is None or index + 1 >= len(days):
        return None
    return days[index + 1]


def _exit_levels(config: Config) -> tuple[float, float]:
    """Per-long stop and profit-take. v6 reads the version-gated model
    fields so v1-v4 stay bit-identical; v5 reads the derivatives section
    (set via replace() in experiments)."""
    if config.model.version == "v6":
        return config.model.v6_stop, config.model.v6_take
    return config.derivatives.stop, config.derivatives.profit_take


def _apply_v5_exits(
    panel: SeriesPanel,
    config: Config,
    days: list[date],
    longs: list[tuple[date, date, bool]],
) -> list[tuple[date, date, bool]]:
    """v5/v6 only: each bottom long carries its own stop and profit-take.

    Economic reason: a bottom long is a reflexive-bounce trade, not a secular
    hold. Without exits the April 2025 long rode the later BTC drawdown into a
    -44% out-of-sample loss. The stop cuts exposure when the bounce fails; the
    target banks the bounce when it works. Checked on daily closes, filled the
    next session like every other signal.
    """
    stop, target = _exit_levels(config)
    if stop <= 0 and target <= 0:
        return longs
    pos = {day: index for index, day in enumerate(days)}
    out = []
    for entry, exit_day, _stopped in longs:
        entry_fill = _next_session(days, entry)
        ref = panel.asof(entry_fill, config.lags).value("btc") if entry_fill else None
        if not ref or entry_fill not in pos or exit_day not in pos:
            out.append((entry, exit_day, False))
            continue
        decided: date | None = None
        hit_stop = False
        for day in days[pos[entry_fill] : pos[exit_day] + 1]:
            price = panel.asof(day, config.lags).value("btc")
            if price is None:
                continue
            if stop > 0 and price <= ref * (1 - stop):
                decided, hit_stop = day, True
                break
            if target > 0 and price >= ref * (1 + target):
                decided, hit_stop = day, False
                break
        if decided is None or decided >= exit_day:
            out.append((entry, exit_day, False))
        else:
            out.append((entry, decided, hit_stop))
    return out


def _simulate_v4(panel: SeriesPanel, config: Config) -> dict[str, Any]:
    """Longs at the bottom, held until the next warning. Puts are optional and reported apart.

    Signals decided on day T fill at the next session: entries, exits and put
    legs are all shifted one session forward. A signal on the final session
    cannot fill and is dropped.
    """
    days = [day for day in panel.dates("spy") if config.window.start <= day <= config.window.end]
    slip = config.costs.perp_slippage_bps / 10_000
    fee = config.costs.perp_fee_bps / 10_000
    path = score_path(panel, scoring_days(panel, config), config)
    size = config.derivatives.long_size
    puts_on = config.model.v4_puts
    long_entry: date | None = None
    long_exit: date | None = None
    longs: list[tuple[date, date, bool]] = []
    puts: list[tuple[date, date]] = []
    put_entry: date | None = None
    for index, day in enumerate(days):
        scored = score_on(path, day) or {}
        bottom = bool(scored.get("bottom"))
        if long_entry is not None and long_exit is None:
            released = not bool(scored.get("redeploy_hold")) and day > long_entry
            if released:
                long_exit = day
                longs.append((long_entry, long_exit, False))
                long_entry = None
                long_exit = None
        if long_entry is None and bottom:
            drawdown = _btc_drawdown(panel, config, day)
            if drawdown is not None and drawdown <= -config.redeploy.btc_drawdown:
                long_entry = day
                long_exit = None
        if puts_on:
            previous = (
                score_on(path, days[index - 1])
                if index
                else score_on(path, day - timedelta(days=1))
            )
            month_end = index + 1 == len(days) or days[index + 1].month != day.month
            if put_entry is None and _warning(previous, scored):
                put_entry = day
            if put_entry is not None and (bottom and day >= put_entry or month_end):
                puts.append((put_entry, day))
                put_entry = None
    if long_entry is not None:
        longs.append((long_entry, days[-1], False))
    if config.model.version in {"v5", "v6"}:
        longs = _apply_v5_exits(panel, config, days, longs)
    # Shift decision days to fill sessions. Entries that cannot fill are dropped;
    # an exit still open at the window end is marked at the last close.
    filled_longs: list[tuple[date, date, bool]] = []
    for entry, exit_day, stopped in longs:
        entry_fill = _next_session(days, entry)
        if entry_fill is None:
            continue
        if exit_day == days[-1] and entry != exit_day:
            filled_longs.append((entry_fill, exit_day, stopped))
        else:
            exit_fill = _next_session(days, exit_day)
            filled_longs.append((entry_fill, exit_fill or exit_day, stopped))
    longs = filled_longs
    filled_puts: list[tuple[date, date]] = []
    for entry, exit_day in puts:
        entry_fill = _next_session(days, entry)
        if entry_fill is None:
            continue
        exit_fill = _next_session(days, exit_day)
        filled_puts.append((entry_fill, exit_fill or exit_day))
    puts = filled_puts
    rows = []
    for members in _months(days):
        long_hits = [
            (entry, exit_day, stopped)
            for entry, exit_day, stopped in longs
            if entry <= members[-1] and exit_day >= members[0]
        ]
        put_hits = [item for item in puts if members[0] <= item[0] <= members[-1]]
        perp_pnl = sum(
            _long_slice(panel, config, days, entry, exit_day, members, size, slip, fee)
            for entry, exit_day, _stopped in long_hits
        )
        put_pnl = 0.0
        pricing = "none"
        strike = None
        premium = None
        for entry, exit_day in put_hits:
            spot = _price_on(panel, config, entry) or 0.0
            leg, pricing, strike, premium = _put_pnl(panel, config, entry, exit_day, spot)
            put_pnl += leg
        hedge = "btc_puts" if put_hits and pricing != "missing" else "none"
        if pricing == "missing":
            put_pnl = 0.0
        active = bool(long_hits) or hedge == "btc_puts"
        total = perp_pnl + (put_pnl if hedge == "btc_puts" else 0.0)
        parts = []
        stopped_here = any(
            stopped and members[0] <= exit_day <= members[-1]
            for _entry, exit_day, stopped in long_hits
        )
        if long_hits:
            parts.append("bottom long")
        if stopped_here:
            parts.append("stopped")
        if hedge == "btc_puts":
            parts.append("warning put")
        opened = bool(long_hits) and members[0] <= long_hits[0][0] <= members[-1]
        if long_hits:
            entry_day, exit_day = long_hits[0][0], long_hits[-1][1]
            first = max(entry_day, members[0])
            last = min(exit_day, members[-1])
            if first == entry_day:
                entry_price = _price_on(panel, config, first) or 0.0
            else:
                entry_price = _price_on(panel, config, days[days.index(first) - 1]) or 0.0
            exit_stamp = last
            exit_price = _price_on(panel, config, last) or entry_price
            anchor = first
        else:
            anchor = put_hits[0][0] if put_hits else members[0]
            exit_stamp = put_hits[-1][1] if put_hits else members[-1]
            entry_price = _price_on(panel, config, anchor) or 0.0
            exit_price = _price_on(panel, config, exit_stamp) or entry_price
        scored = score_on(path, anchor) or {}
        rows.append(
            {
                "month": members[0].strftime("%Y-%m"),
                "date": members[0].isoformat(),
                "entry_date": long_hits[0][0].isoformat() if opened else None,
                "opened": opened,
                "signal": " + ".join(parts) if parts else "flat",
                "regime": scored.get("regime", "neutral"),
                "position": "long" if long_hits else "flat",
                "size": size if long_hits else 0.0,
                "entry": entry_price,
                "exit": exit_price,
                "exit_date": exit_stamp.isoformat(),
                "stopped": stopped_here,
                "funding_pnl": 0.0,
                "fees": 0.0,
                "perp_pnl": perp_pnl,
                "hedge": hedge,
                "hedge_signal": hedge == "btc_puts",
                "strike": strike,
                "premium": premium,
                "hedge_pnl": put_pnl if hedge == "btc_puts" else None,
                "pricing": pricing,
                "pnl": total,
                "success": (total > 0) if active else None,
                "options": "n/a",
            }
        )
    oos = config.window.oos_start
    in_rows = [row for row in rows if date.fromisoformat(row["date"]) < oos]
    out_rows = [row for row in rows if date.fromisoformat(row["date"]) >= oos]
    put_note = (
        "Puts are opened on a fresh warning and marked to the bottom or month-end."
        if puts_on
        else "Puts are off in this configuration."
    )
    return {
        "rows": rows,
        "full": _summarize(rows),
        "in_sample": _summarize(in_rows),
        "out_of_sample": _summarize(out_rows),
        "pricing_note": (
            "v4 opens a BTC long only on the buy-the-low signal and holds it until the next "
            "caution or risk-off after a quiet day. "
            f"{put_note} "
            "Puts are Black-Scholes on Deribit DVOL when that print exists, otherwise realized vol. "
            "Each expression is still scaled as a fraction of one BTC."
        ),
    }


def simulate_derivatives(panel: SeriesPanel, config: Config) -> dict[str, Any]:
    if config.model.version in {"v4", "v5", "v6"}:
        return _simulate_v4(panel, config)
    if config.model.version == "v3":
        return _simulate_timed(panel, config)
    days = [day for day in panel.dates("btc") if config.window.start <= day <= config.window.end]
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
                premium = bs_put(
                    entry,
                    strike,
                    years,
                    iv + config.costs.option_iv_slippage,
                    _rate(panel, config, entry_day),
                )
                remaining_days = (
                    entry_day + timedelta(days=config.derivatives.put_tenor_days) - exit_day
                ).days
                exit_iv, _source = _iv(panel, config, exit_day)
                mark = bs_put(
                    exit_price,
                    strike,
                    max(remaining_days, 0) / 365.25,
                    exit_iv if exit_iv is not None else iv,
                    _rate(panel, config, exit_day),
                )
                option_fees = entry * (config.costs.option_fee_bps_underlying / 10_000) * 2
                # Premium, mark and fees are USD per BTC. P&L is a fraction of the entry spot.
                hedge_pnl = (mark - premium - option_fees) / entry
        total = perp_pnl + (hedge_pnl or 0.0)
        active = direction != "flat" or hedge == "btc_puts"
        rows.append(
            {
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
            }
        )
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
