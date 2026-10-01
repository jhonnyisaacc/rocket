"""Family B: buy-the-capitulation BTC longs, one leg at a time.

Entries (one per variant): DVOL spike-then-fade, deeply negative funding,
or peak drawdown beyond X. Exits per leg: fixed stop, profit target, time
stop, trailing stop — whichever arms first. Decisions on bar T fill at bar
T+1's OPEN (next-bar fills). Sizing is 1x spot unless size_mult says
otherwise (perps overlay accrues the venue-median daily funding while
open). Report per-leg and per-crash results; drop rules whose edge comes
from a single episode.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from rocket.crypto.data import CRASHES, Bar


@dataclass(frozen=True)
class LongRule:
    """One capitulation-long variant. At most 5 free params per protocol."""

    entry: str = "drawdown"  # drawdown | funding | dvol_fade
    drawdown: float = 0.30  # peak drawdown that arms a buy
    funding_neg: float = -0.0005  # daily funding at or below which we buy
    dvol_spike: float = 80.0  # DVOL level marking the spike
    dvol_fade_days: int = 5  # fade horizon after the spike
    stop: float = 0.15
    target: float = 0.30
    time_stop_days: int = 90
    trailing: float = 0.20  # 0 disables the trailing exit
    size_mult: float = 1.0  # 1 = spot; 2 = 2x perps overlay


@dataclass
class Leg:
    entry_day: date
    entry_price: float
    exit_day: date
    exit_price: float
    exit_why: str
    leg_return: float


def run_longs(
    bars: list[Bar],
    vols: dict[date, float],
    funding: dict[date, dict[str, float]],
    rule: LongRule,
) -> dict:
    closes = [b.close for b in bars]
    peak = closes[0]
    pending: float | None = None  # entry price signal, fills next open
    position: dict | None = None
    legs: list[Leg] = []
    funding_paid = 0.0

    def median_funding(day: date) -> float | None:
        venues = funding.get(day)
        if not venues:
            return None
        rates = sorted(venues.values())
        return rates[len(rates) // 2]

    def dvol_spike_faded(i: int) -> bool:
        day = bars[i].day
        if day not in vols:
            return False
        window = [vols.get(bars[j].day) for j in range(max(0, i - 30), i + 1)]
        window = [v for v in window if v is not None]
        if not window:
            return False
        spike = max(window)
        if spike < rule.dvol_spike:
            return False
        recent = [v for v in window[-rule.dvol_fade_days :] if v is not None]
        return bool(recent) and recent[-1] < spike * 0.8 and vols[day] < spike

    for i in range(len(bars)):
        bar = bars[i]
        peak = max(peak, bar.close)
        # Manage the open position at today's close (exit decisions).
        if position is not None:
            peak_since = max(position["peak"], bar.close)
            position["peak"] = peak_since
            ref = position["entry"]
            why = None
            if bar.close <= ref * (1 - rule.stop):
                why = "stop"
            elif bar.close >= ref * (1 + rule.target):
                why = "target"
            elif rule.trailing > 0 and bar.close <= peak_since * (1 - rule.trailing):
                why = "trailing"
            elif (bar.day - position["day"]).days >= rule.time_stop_days:
                why = "time"
            if why is not None and i + 1 < len(bars):
                position["exit_decided"] = (bar.day, why)
        # Fills at this bar's open: exits decided on bar i-1, entries
        # decided on bar i-1 open after the prior bar's exit cleared.
        if position is not None and "exit_decided" in position:
            _, why = position["exit_decided"]
            ret = bar.open / position["entry"] - 1
            legs.append(Leg(position["day"], position["entry"], bar.day, bar.open, why, ret))
            position = None
            continue
        if position is None and pending is not None:
            position = {"day": bar.day, "entry": bar.open, "peak": bar.open}
            pending = None
            continue
        if position is None and pending is None:
            dd = bar.close / peak - 1 if peak > 0 else 0.0
            fire = False
            if rule.entry == "drawdown":
                fire = dd <= -rule.drawdown
            elif rule.entry == "funding":
                rate = median_funding(bar.day)
                fire = rate is not None and rate <= rule.funding_neg
            elif rule.entry == "dvol_fade":
                fire = dvol_spike_faded(i)
            if fire:
                pending = bar.close
        # Accrue venue-median funding while a perps overlay is open.
        if position is not None and rule.size_mult > 1.0:
            rate = median_funding(bar.day)
            if rate is not None:
                funding_paid += rate * (rule.size_mult - 1.0)

    if position is not None:
        # No next bar exists: settle at the last close, labeled as such.
        ret = bars[-1].close / position["entry"] - 1
        legs.append(
            Leg(
                position["day"],
                position["entry"],
                bars[-1].day,
                bars[-1].close,
                "truncated",
                ret,
            )
        )
        position = None

    equity = 1.0
    for leg in legs:
        equity *= 1 + leg.leg_return * rule.size_mult
    equity *= 1 - funding_paid
    return {
        "legs": [
            {
                "entry": leg.entry_day.isoformat(),
                "exit": leg.exit_day.isoformat(),
                "why": leg.exit_why,
                "return": round(leg.leg_return * 100, 1),
            }
            for leg in legs
        ],
        "n_legs": len(legs),
        "equity": round(equity, 4),
        "funding_paid": round(funding_paid * 100, 2),
    }


def crash_legs(result: dict, bars: list[Bar]) -> list[dict]:
    """Legs grouped by crash window, for the per-crash table."""
    out = []
    for name, start_s, end_s in CRASHES:
        legs = [leg for leg in result["legs"] if start_s <= leg["entry"] <= end_s]
        if not legs:
            continue
        rets = [leg["return"] for leg in legs]
        out.append(
            {
                "crash": name,
                "legs": len(legs),
                "avg_return": round(sum(rets) / len(rets), 1),
                "worst": round(min(rets), 1),
            }
        )
    return out
