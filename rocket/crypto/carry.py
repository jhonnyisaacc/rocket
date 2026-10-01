"""Family C: funding carry, market-neutral by construction.

When venue-median daily funding is above +threshold, hold short-perp /
long-spot into the next bar; when below -threshold, the reverse. Both legs
fill at the next open; each flip pays taker fees on both legs plus a
slippage haircut, and the perp leg accrues realized funding daily. Reports
return, max drawdown, and the capacity/exchange-risk caveats (as text —
they do not fit in a backtest).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from rocket.crypto.data import Bar

# Round-trip frictions per flip, in fractions of notional.
SPOT_TAKER = 0.0010
PERP_TAKER = 0.0005
SLIPPAGE = 0.0002


@dataclass(frozen=True)
class CarryRule:
    """One carry variant. At most 5 free params per protocol."""

    funding_threshold: float = 0.0003  # daily funding that arms the trade
    hold_days: int = 1  # minimum holding before a flip is allowed


def run_carry(
    bars: list[Bar],
    funding: dict[date, dict[str, float]],
    rule: CarryRule,
) -> dict:
    closes = {b.day: b.close for b in bars}
    opens = {b.day: b.open for b in bars}
    days = [b.day for b in bars]

    def median(day: date) -> float | None:
        venues = funding.get(day)
        if not venues:
            return None
        rates = sorted(venues.values())
        return rates[len(rates) // 2]

    position = 0  # +1 = short perp / long spot, -1 = reverse, 0 = flat
    pending: int | None = None  # decided side, fills next open
    held = 0
    equity = 1.0
    path = [1.0]
    flips = 0
    earned = 0.0

    for i, day in enumerate(days):
        rate = median(day)
        # Accrue today's funding on the open carry position.
        if position != 0 and rate is not None:
            # Short perp earns positive funding; long perp pays it.
            earned += position * rate
            equity *= 1 + position * rate
        path.append(equity)
        if i + 1 >= len(days):
            break
        # Decide the side for tomorrow on today's print (next-bar fills).
        if rate is None:
            want = 0
        elif rate >= rule.funding_threshold:
            want = 1
        elif rate <= -rule.funding_threshold:
            want = -1
        else:
            want = 0
        held += 1
        if pending is not None:
            if pending != position:
                equity *= 1 - (SPOT_TAKER + PERP_TAKER + SLIPPAGE)
                flips += 1
                position = pending
                held = 0
            pending = None
            continue
        if want != position and held >= rule.hold_days:
            pending = want

    dd = 0.0
    peak = path[0]
    for value in path:
        peak = max(peak, value)
        if peak > 0:
            dd = min(dd, value / peak - 1)
    years = max((days[-1] - days[0]).days / 365.0, 1 / 365)
    return {
        "equity": round(equity, 4),
        "total_return": round(equity - 1, 4),
        "max_drawdown": round(dd, 4),
        "annualized": round((equity) ** (1 / years) - 1, 4),
        "flips": flips,
        "funding_earned": round(earned, 4),
        "caveats": [
            "Capacity: extreme funding prints coincide with wide spreads "
            "and thin books; size fills at worse than the mark.",
            "Exchange risk: a market-neutral book is still exposed to venue "
            "outage, clawback, and margin-currency moves; FTX 2022 is the "
            "proof that venue risk is not theoretical.",
            "Regime risk: funding is a crowded premium; post-2023 prints "
            "are thinner than 2020-2021.",
        ],
    }
