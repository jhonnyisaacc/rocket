import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "artifacts" / "futures_desk" / "bakeoff" / "tape_score.py"
_SPEC = importlib.util.spec_from_file_location("tape_score", _PATH)
ts = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ts)


def _bar(t, o, h, l, c, v=1.0):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}


def test_clip_drops_bars_before_measured_tape():
    early = ts.TAPE_START_MS - ts.H
    rows = [
        _bar(early, 1, 2, 1, 1.5),
        _bar(ts.TAPE_START_MS, 1, 2, 1, 1.5),
        _bar(ts.TAPE_LAST_MS, 3, 9, 0.1, 8),
    ]
    clipped = ts.clip_tape_1h(rows)
    assert [bar["t"] for bar in clipped] == [ts.TAPE_START_MS, ts.TAPE_LAST_MS]
    assert clipped[-1]["_fill_only"] is True
    assert clipped[-1]["h"] == clipped[-1]["o"]
    assert clipped[-1]["l"] == clipped[-1]["o"]


def test_quintile_floor_and_book_below_five():
    assert ts.quintile_sides([("A", 1.0), ("B", 2.0), ("C", 3.0), ("D", 4.0)]) is None
    longs, shorts = ts.quintile_sides(
        [
            ("A", 1),
            ("B", 2),
            ("C", 3),
            ("D", 4),
            ("E", 5),
            ("F", 6),
            ("G", 7),
            ("H", 8),
            ("I", 9),
            ("J", 10),
        ]
    )
    assert shorts == ["A", "B"]
    assert longs == ["I", "J"]
    assert set(shorts).isdisjoint(longs)


def test_trb_fresh_cross_uses_days_closed_before_the_4h_open():
    day = ts.DAY
    start = ts.TAPE_START_MS
    daily = []
    for index in range(60):
        open_t = start - 80 * day + index * day
        daily.append(_bar(open_t, 100, 110, 90, 100 + index))
    signal_open = start
    h4 = [
        _bar(signal_open - ts.H4, 150, 160, 140, 158),
        _bar(signal_open, 159, 170, 150, 169),
    ]
    signals = ts.trb_signals(daily, h4)
    assert signals
    assert signals[0]["direction"] == 1
    assert signals[0]["close_t"] == signal_open + ts.H4
    again = ts.trb_signals(daily, h4 + [_bar(signal_open + ts.H4, 170, 180, 160, 175)])
    assert len(again) == 1


def test_month_list_uses_last_completed_daily_notional_only():
    start = int(datetime(2026, 3, 1, tzinfo=UTC).timestamp() * 1000)
    daily = {
        "BTC": [_bar(start - 2 * ts.DAY, 1, 1, 1, 100, v=60_000)],
        "TINY": [_bar(start - 2 * ts.DAY, 1, 1, 1, 10, v=10)],
        "NEW": [_bar(start - ts.H, 1, 1, 1, 100, v=1_000_000)],
    }
    # March membership is index 1 in MONTH_STARTS.
    membership = ts.month_membership(daily)
    march = membership[1]
    assert "BTC" in march
    assert "TINY" not in march
    assert "NEW" not in march


def test_funding_drag_does_not_zero_fill_a_gap():
    entry = ts.TAPE_START_MS
    drag, complete = ts.funding_drag(1, 100.0, entry, entry + 2 * ts.H, {entry + ts.H: 0.001})
    assert complete is False
    assert drag is None
    drag, complete = ts.funding_drag(
        1, 100.0, entry, entry + 2 * ts.H, {entry + ts.H: 0.001, entry + 2 * ts.H: 0.002}
    )
    assert complete is True
    assert drag == pytest.approx(0.3)


def test_path_orders_disagree_when_stop_and_target_share_a_bar():
    bar = _bar(ts.TAPE_START_MS, 100, 130, 80, 110)
    long_stop, long_target = 90, 120
    olhc = ts.path_exit([bar], 1, long_stop, long_target, "OLHC")
    ohlc = ts.path_exit([bar], 1, long_stop, long_target, "OHLC")
    assert olhc["reason"] == "stop"
    assert ohlc["reason"] == "target"
