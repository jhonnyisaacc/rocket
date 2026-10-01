"""Read-only Perps readout for the daily check.

Informational only: no family earned a live trade signal (see
docs/crypto/BACKTEST.md), so every line reports market state plus the
researched stance. Never places orders; holds no keys.
"""

from __future__ import annotations

from datetime import date

from rocket.crypto.data import Bar

HEDGE_STANCE = (
    "no: puts cost 11-18%/yr for +4pp OOS drawdown reduction and made the "
    "2026 holdout drawdown worse (-44.2% vs -39.5% naked)"
)


def trailing_dvol_pct(vols: dict[date, float], day: date) -> float | None:
    """Causal trailing-252-print DVOL percentile for `day`, or None."""
    ordered = sorted(vols.items())
    hist = [value for dvol_day, value in ordered if dvol_day < day]
    if len(hist) < 63 or day not in vols:
        return None
    window = hist[-252:]
    below = sum(1 for value in window if value <= vols[day])
    return 100.0 * below / len(window)


def median_funding(funding: dict[date, dict[str, float]], day: date) -> float | None:
    venues = funding.get(day)
    if not venues:
        return None
    rates = sorted(venues.values())
    return rates[len(rates) // 2]


def drawdown_from_high(bars: list[Bar], day: date, lookback: int = 90) -> float | None:
    idx = next((k for k, bar in enumerate(bars) if bar.day == day), None)
    if idx is None:
        return None
    closes = [bar.close for bar in bars[max(0, idx - lookback + 1) : idx + 1]]
    high = max(closes)
    return closes[-1] / high - 1 if high > 0 else None


def perps_snapshot(
    bars: list[Bar],
    vols: dict[date, float],
    funding: dict[date, dict[str, float]],
    previous: dict | None = None,
) -> dict:
    """Build the Perps readout for the latest shared data day."""
    days = {bar.day for bar in bars} & set(vols)
    if funding:
        days &= set(funding)
    if not days:
        return {"status": "no-overlapping-data", "lines": {}, "changed": {}}
    day = max(days)
    pct = trailing_dvol_pct(vols, day)
    dvol_bucket = "unknown" if pct is None else (
        "cheap" if pct <= 25 else ("rich" if pct >= 75 else "fair"))
    dip = drawdown_from_high(bars, day)
    fund = median_funding(funding, day)
    fund_ann = None if fund is None else fund * 365 * 100
    carry_bucket = "unknown" if fund_ann is None else (
        "rich" if fund_ann >= 10 else ("fair" if fund_ann >= 3 else "thin"))
    lines = {
        "puts": {"dvol_percentile": None if pct is None else round(pct, 1),
                 "vol_bucket": dvol_bucket, "hedge": "no", "why": HEDGE_STANCE},
        "dip": {"drawdown_pct": None if dip is None else round(dip * 100, 1),
                "signal": "none",
                "why": "dip-buy expectancy (+7%/leg) is luck-indistinguishable (DSR 0.00)"},
        "carry": {"funding_ann_pct": None if fund_ann is None else round(fund_ann, 2),
                  "carry_bucket": carry_bucket, "signal": "weak-or-flat",
                  "why": "carry is regime-thin ex-2021 (+1%/yr) and -0.55% in holdout"},
    }
    prev_lines = (previous or {}).get("lines", {})
    changed = {key: prev_lines.get(key) != line for key, line in lines.items()}
    return {"status": "ok", "as_of": day.isoformat(), "lines": lines,
            "changed": changed, "changed_any": any(changed.values())}
