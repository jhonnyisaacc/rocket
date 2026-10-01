"""Family A: BTC puts as insurance, judged as insurance, not a profit trade.

A variant buys 10-20% OTM puts on a trigger (cheap vol, pre-event, stress
warning, or a fixed monthly roll baseline), prices them Black-Scholes on
DVOL (realized vol before 2021-04) with a skew markup, and holds them to a
fixed exit. Decisions on bar T fill at bar T+1's OPEN (next-bar fills).
Reports: cost per year, BTC+puts drawdown vs BTC-alone drawdown, and the
payoff in each crash window.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from rocket.crypto.data import Bar, CRASHES
from rocket.market_check.bs import bs_put

YEAR = 365.0
# Skew markup: 10-20% OTM BTC puts trade above ATM. Multiplying ATM IV by
# SKEW understates the insurance edge (overstates cost). APPROXIMATION:
# no free historical skew surface was found.
SKEW = 1.10
# Deribit taker fee for options: 0.03% of underlying per contract.
FEE_RATE = 0.0003
# Half-spread proxy on the premium when no spread history exists.
HALF_SPREAD = 0.10


@dataclass(frozen=True)
class PutRule:
    """One insurance variant. At most 5 free params per family protocol."""

    tenor_days: int = 90  # fixed time to expiry at purchase
    otm: float = 0.15  # strike = (1 - otm) * spot
    trigger: str = "monthly"  # monthly | cheap_vol | pre_event | stress
    cheap_vol_pct: float = 25.0  # DVOL percentile at or below which vol is cheap
    pre_event_days: int = 7  # buy N days before FOMC/election
    exit_dte: int = 0  # days to expiry at exit (0 = hold to expiry)


@dataclass
class Leg:
    entry_day: date
    expiry_day: date
    strike: float
    contracts: float  # in BTC notional units of 1 BTC
    premium_each: float
    exit_day: date | None = None
    exit_each: float = 0.0


def realized_vol(closes: list[float], window: int = 30) -> float | None:
    if len(closes) < window + 1:
        return None
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    tail = rets[-window:]
    mean = sum(tail) / window
    var = sum((r - mean) ** 2 for r in tail) / (window - 1)
    return math.sqrt(var * YEAR)


def buy_premium(spot: float, strike: float, tenor_years: float, iv: float) -> float:
    mid = bs_put(spot, strike, tenor_years, 0.0, iv)
    fee = FEE_RATE * spot
    return mid * (1 + HALF_SPREAD) + fee


def exit_value(
    spot: float, strike: float, remaining_years: float, iv: float,
) -> float:
    if remaining_years <= 0:
        return max(strike - spot, 0.0)
    mid = bs_put(spot, strike, remaining_years, 0.0, iv)
    fee = FEE_RATE * spot
    return max(mid * (1 - HALF_SPREAD) - fee, 0.0)


def run_insurance(
    bars: list[Bar],
    vols: dict[date, float],
    rule: PutRule,
    events: list[date] | None = None,
    stress_days: set[date] | None = None,
    notional_btc: float = 1.0,
) -> dict:
    """Simulate one BTC unit protected by puts bought per rule.

    Returns spend, yearly cost, combined vs naked drawdowns, and legs.
    """
    closes = [b.close for b in bars]
    dvol_hist = sorted(v for _, v in vols.items())

    def vol_at(index: int) -> float:
        day = bars[index].day
        if day in vols:
            return vols[day] * SKEW
        rv = realized_vol(closes[: index + 1])
        return (rv or 0.5) * SKEW

    def percentile(value: float) -> float:
        if not dvol_hist:
            return 100.0
        below = sum(1 for v in dvol_hist if v <= value)
        return 100.0 * below / len(dvol_hist)

    pending_close: float | None = None  # decided bar T, fills bar T+1 open
    legs: list[Leg] = []
    open_legs: list[Leg] = []
    spend = 0.0
    event_set = set(events or [])
    combined: list[float] = []

    for i in range(len(bars)):
        bar = bars[i]
        iv = vol_at(i)
        # Mark open legs at today's close, exiting at exit_dte.
        alive: list[Leg] = []
        for leg in open_legs:
            remaining = (leg.expiry_day - bar.day).days
            if remaining <= rule.exit_dte:
                leg.exit_day = bar.day
                leg.exit_each = exit_value(
                    bar.close, leg.strike, max(remaining, 0) / YEAR, iv / SKEW
                )
                continue
            alive.append(leg)
        open_legs = alive
        # Combined NAV: spot plus the live value of open protection.
        day_mark = 0.0
        for leg in open_legs:
            remaining = max((leg.expiry_day - bar.day).days, 0) / YEAR
            mark = exit_value(bar.close, leg.strike, remaining, iv / SKEW)
            day_mark += (mark - leg.premium_each) * leg.contracts
        combined.append(bar.close * notional_btc + day_mark)
        # Fill the pending purchase (decided on bar i-1) at this bar's open.
        if pending_close is not None:
            tenor = rule.tenor_days / YEAR
            strike = (1 - rule.otm) * pending_close
            premium = buy_premium(bar.open, strike, tenor, iv)
            expiry = add_days(bar.day, rule.tenor_days)
            fill = bar
            open_legs.append(Leg(fill.day, expiry, strike, notional_btc, premium))
            spend += premium * notional_btc
            legs.append(open_legs[-1])
            pending_close = None
            continue
        # Decide a new purchase on bar i (fills bar i+1).
        trigger = False
        if rule.trigger == "monthly":
            trigger = not legs or (bar.day - legs[-1].entry_day).days >= 30
        elif rule.trigger == "cheap_vol":
            trigger = percentile(vols.get(bar.day, 1e9)) <= rule.cheap_vol_pct
        elif rule.trigger == "pre_event":
            trigger = any(
                0 < (event - bar.day).days <= rule.pre_event_days for event in event_set
            )
        elif rule.trigger == "stress":
            trigger = bar.day in (stress_days or set())
        if trigger:
            pending_close = bar.close

    for leg in open_legs:
        if leg.exit_day is None:
            leg.exit_day = bars[-1].day
            remaining = max((leg.expiry_day - bars[-1].day).days, 0) / YEAR
            leg.exit_each = exit_value(
                bars[-1].close, leg.strike, remaining, vol_at(len(bars) - 1) / SKEW
            )
    return {
        "spend": spend,
        "legs": [
            {
                "entry": leg.entry_day.isoformat(),
                "strike": round(leg.strike, 1),
                "premium": round(leg.premium_each, 1),
                "exit": leg.exit_day.isoformat() if leg.exit_day else None,
                "exit_value": round(leg.exit_each, 1),
            }
            for leg in legs
        ],
        "combined": combined,
        "naked": [b.close * notional_btc for b in bars],
    }


def add_days(day: date, n: int) -> date:
    from datetime import timedelta

    return day + timedelta(days=n)


def max_dd(path: list[float]) -> float:
    peak = path[0]
    worst = 0.0
    for value in path:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1)
    return worst


def crash_payoffs(result: dict, bars: list[Bar]) -> list[dict]:
    """Per-crash payoff of the insured vs naked path (rebased at window start)."""
    days = [b.day for b in bars]
    out = []
    for name, start_s, end_s in CRASHES:
        start, end = date.fromisoformat(start_s), date.fromisoformat(end_s)
        idx = [i for i, d in enumerate(days) if start <= d <= end]
        if len(idx) < 2:
            continue
        base_naked = result["naked"][idx[0]] or 1.0
        base_hedged = result["combined"][idx[0]] or 1.0
        naked_dd = min(result["naked"][i] / base_naked - 1 for i in idx)
        hedged_dd = min(result["combined"][i] / base_hedged - 1 for i in idx)
        out.append(
            {
                "crash": name,
                "naked_dd": round(naked_dd * 100, 1),
                "hedged_dd": round(hedged_dd * 100, 1),
                "dd_reduction_pp": round((hedged_dd - naked_dd) * 100, 1),
            }
        )
    return out
