from datetime import date, timedelta

from rocket.crypto.data import Bar
from rocket.crypto.perps import (
    drawdown_from_high,
    median_funding,
    perps_snapshot,
    trailing_dvol_pct,
)


def _bars(start: date, closes: list[float]) -> list[Bar]:
    return [
        Bar(day=start + timedelta(days=i), open=c, high=c, low=c, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]


def test_trailing_percentile_needs_history():
    vols = {date(2021, 1, 1) + timedelta(days=i): 90.0 for i in range(10)}
    assert trailing_dvol_pct(vols, date(2021, 1, 11)) is None


def test_trailing_percentile_ranks_causally():
    start = date(2021, 1, 1)
    vols = {start + timedelta(days=i): 90.0 for i in range(100)}
    vols[start + timedelta(days=100)] = 50.0
    assert trailing_dvol_pct(vols, start + timedelta(days=100)) == 0.0


def test_snapshot_lines_and_changed_flag():
    start = date(2021, 6, 1)
    closes = [100.0] * 100 + [85.0]
    bars = _bars(start, closes)
    vols = {start + timedelta(days=i): 90.0 for i in range(100)}
    vols[start + timedelta(days=100)] = 50.0
    funding = {start + timedelta(days=100): {"binance": 0.0001}}
    first = perps_snapshot(bars, vols, funding)
    assert first["status"] == "ok"
    assert first["lines"]["puts"]["vol_bucket"] == "cheap"
    assert first["lines"]["puts"]["hedge"] == "no"
    assert first["lines"]["dip"]["drawdown_pct"] == -15.0
    assert first["changed_any"] is True
    second = perps_snapshot(bars, vols, funding, previous=first)
    assert second["changed_any"] is False


def test_snapshot_no_overlap():
    assert perps_snapshot([], {}, {})["status"] == "no-overlapping-data"


def test_median_funding_missing_day():
    assert median_funding({}, date(2021, 1, 1)) is None
    assert drawdown_from_high([], date(2021, 1, 1)) is None
