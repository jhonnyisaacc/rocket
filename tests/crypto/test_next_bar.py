"""Next-bar fills: decisions on bar T execute at bar T+1, never at T."""

from datetime import date, timedelta

from rocket.crypto import carry as carry_mod
from rocket.crypto import longs as longs_mod
from rocket.crypto import puts as puts_mod
from rocket.crypto.data import Bar


def _bars(days: int = 120, crash_at: int = 60) -> list[Bar]:
    out = []
    day = date(2023, 1, 2)
    price = 100.0
    while len(out) < days:
        if day.weekday() < 7:
            if len(out) == crash_at:
                price *= 0.7
            out.append(Bar(day, price, price * 1.01, price * 0.99, price, 1000.0))
            price *= 1.001
        day += timedelta(days=1)
    return out


def _shock_open(bars: list[Bar], index: int, mult: float) -> list[Bar]:
    changed = []
    for i, bar in enumerate(bars):
        if i == index:
            changed.append(
                Bar(bar.day, bar.open * mult, bar.high * mult,
                    bar.low, bar.close, bar.volume)
            )
        else:
            changed.append(bar)
    return changed


def test_put_fill_uses_next_open():
    bars = _bars()
    vols = {b.day: 50.0 for b in bars}
    rule = puts_mod.PutRule(tenor_days=30, otm=0.15, trigger="monthly")
    base = puts_mod.run_insurance(bars, vols, rule)
    assert base["legs"], "monthly roll must buy puts"
    first = base["legs"][0]
    assert first["entry"] == bars[1].day.isoformat(), "first decision fills next bar"
    moved = puts_mod.run_insurance(_shock_open(bars, 1, 2.0), vols, rule)
    assert moved["legs"][0]["premium"] != first["premium"]
    assert moved["legs"][0]["premium"] > first["premium"]


def test_long_fill_uses_next_open():
    bars = _bars()
    vols = {b.day: 50.0 for b in bars}
    funding = {b.day: {"binance": 0.0001} for b in bars}
    rule = longs_mod.LongRule(entry="drawdown", drawdown=0.2, stop=0.5, target=0.05,
                              time_stop_days=200, trailing=0.0)
    base = longs_mod.run_longs(bars, vols, funding, rule)
    assert base["n_legs"] >= 1
    entry_idx = next(i for i, b in enumerate(bars) if b.day.isoformat() == base["legs"][0]["entry"])
    assert entry_idx > 0, "entry must fill the bar after the signal"
    moved = longs_mod.run_longs(_shock_open(bars, entry_idx, 1.5), vols, funding, rule)
    assert moved["legs"][0]["return"] != base["legs"][0]["return"]


def test_carry_reacts_next_bar_not_same_bar():
    bars = _bars()
    days = [b.day for b in bars]
    funding = {d: {"binance": 0.0001, "bybit": 0.0001} for d in days}
    funding[days[50]] = {"binance": 0.01, "bybit": 0.01}
    rule = carry_mod.CarryRule(funding_threshold=0.001)
    base = carry_mod.run_carry(bars, funding, rule)
    calm = dict(funding)
    calm[days[50]] = {"binance": 0.0001, "bybit": 0.0001}
    plain = carry_mod.run_carry(bars, calm, rule)
    assert base["flips"] > plain["flips"], "extreme print must open carry"
    assert base["equity"] != plain["equity"]
