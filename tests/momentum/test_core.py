import math
from dataclasses import replace

import pytest

from rocket.momentum.core import (
    DAY,
    FOUR_HOURS,
    HOUR,
    LAG,
    Bar,
    CandidateEvent,
    Observation,
    ResearchFold,
    aggregate_four_hours,
    candidates,
    fingerprint,
    interval_groups,
    label,
    pit_join,
    snapshot,
    spaced_events,
)


def bar(t, p=100.0, high=None, low=None, interval=HOUR):
    return Bar(t, t + interval, t + interval + LAG, 0, p, high or p, low or p, p, 10.0)


def history(n=190):
    return [bar(i * FOUR_HOURS, 100 + math.sin(i) * 0.2, interval=FOUR_HOURS) for i in range(n)]


def event(side=1):
    return CandidateEvent("e", LAG, 0, side, 100.0, 0.05, "s")


def forward():
    return [bar(i * HOUR) for i in range(1, 7 * 24)]


def test_pit_publication_vintage_receipt_and_unknown():
    rows = [
        Observation("x", 1.0, 0, 5, 6, "src", "v1"),
        Observation("x", 2.0, 0, 20, 21, "src", "v2"),
        Observation("unknown", 0.0, 0, None, 1, "src", "v1"),
    ]
    assert pit_join(rows, 10)["x"].value == 1.0
    assert "unknown" not in pit_join(rows, 10)
    assert pit_join(rows, 25)["x"].value == 2.0
    assert pit_join(rows, 5, prospective=True) == {}
    assert pit_join(rows, 6, prospective=True)["x"].value == 1.0
    assert pit_join(rows + [Observation("future", 1.0, 50, 5, 6, "src", "v1")], 10) == pit_join(
        rows, 10
    )


def test_pit_conflicting_revision_identity_rejected():
    a = Observation("x", 1.0, 0, 5, 6, "src", "v1")
    with pytest.raises(ValueError):
        pit_join([a, replace(a, value=2.0)], 10)


def test_bar_clocks_aggregation_and_missing_hours():
    assert aggregate_four_hours([bar(i * HOUR) for i in range(4)])[0].end_time == FOUR_HOURS
    assert aggregate_four_hours([bar(i * HOUR) for i in (0, 1, 3)]) == []
    with pytest.raises(ValueError):
        aggregate_four_hours([bar(0), bar(0)])
    with pytest.raises(ValueError):
        bar(1) and aggregate_four_hours([bar(1)])
    with pytest.raises(ValueError):
        replace(bar(0), available_at=HOUR - 1)


def test_snapshot_future_mutation_invariance_and_schema():
    rows = history()
    cutoff = rows[180].end_time
    a = snapshot(rows, cutoff + LAG, cutoff)
    future = [replace(b, open=500.0, high=500.0, low=500.0, close=500.0) for b in rows[181:]]
    b = snapshot(rows[:181] + future + [future[0]], cutoff + LAG, cutoff)
    assert a == b
    assert a.identity == b.identity
    assert replace(a, schema="next").identity != a.identity
    assert a.values["oi_change_24h"] is None
    assert "oi_change_24h" in a.unknown


def test_missing_stale_and_late_bar_are_unknown():
    rows = history(181)
    cutoff = rows[-1].end_time
    assert snapshot(rows[1:], cutoff + LAG, cutoff).state == "UNKNOWN"
    assert snapshot(rows[:-1], cutoff + LAG, cutoff).state == "UNKNOWN"
    late = rows[:-1] + [replace(rows[-1], available_at=cutoff + LAG + 1)]
    assert snapshot(late, cutoff + LAG, cutoff).state == "UNKNOWN"
    receipt = rows[:-1] + [replace(rows[-1], ingested_at=cutoff + LAG + 1)]
    assert snapshot(receipt, cutoff + LAG, cutoff, prospective=True).state == "UNKNOWN"
    with pytest.raises(ValueError):
        snapshot(rows, cutoff, cutoff)


@pytest.mark.parametrize("side", [1, -1])
def test_triple_barrier_success_and_failure(side):
    rows = forward()
    price = 100 * math.exp(side * 0.11)
    rows[0] = bar(HOUR, price)
    assert label(event(side), rows).outcome == ("CONTINUES_UP" if side == 1 else "CONTINUES_DOWN")
    price = 100 * math.exp(-side * 0.06)
    rows[0] = bar(HOUR, price)
    assert label(event(side), rows).outcome == "FAILS"


def test_first_hit_timeout_unknown_and_signal_bar_excluded():
    rows = forward()
    assert label(event(), rows).outcome == "TIMEOUT"
    assert label(event(), rows[:-1]).reason == "INCOMPLETE_HORIZON"
    rows[0] = bar(HOUR, high=112.0, low=94.0)
    assert label(event(), rows).reason == "AMBIGUOUS_INTRABAR_ORDER"
    rows[0] = bar(HOUR, 94.0)
    rows[1] = bar(2 * HOUR, 112.0)
    assert label(event(), rows).outcome == "FAILS"
    assert label(event(), [bar(0, high=112.0, low=94.0)] + forward()).outcome == "TIMEOUT"
    assert label(event(), forward() + [bar(7 * DAY, high=200.0)]) == label(event(), forward())


@pytest.mark.parametrize(
    "favorable,adverse,outcome",
    [
        (0.11, -0.01, "CONTINUES"),
        (0.01, -0.06, "FAILS"),
        (0.11, -0.06, "UNKNOWN"),
        (0.01, -0.01, "TIMEOUT"),
    ],
)
def test_ohlc_barrier_geometry_is_log_mirrored(favorable, adverse, outcome):
    results = []
    for side in (1, -1):
        good = 100 * math.exp(side * favorable)
        bad = 100 * math.exp(side * adverse)
        rows = forward()
        rows[0] = bar(HOUR, high=max(good, bad), low=min(good, bad))
        result = label(event(side), rows)
        expected = (
            f"CONTINUES_{'UP' if side == 1 else 'DOWN'}" if outcome == "CONTINUES" else outcome
        )
        assert result.outcome == expected
        assert result.barrier_time == (None if outcome == "TIMEOUT" else 2 * HOUR)
        assert result.reason == ("AMBIGUOUS_INTRABAR_ORDER" if outcome == "UNKNOWN" else None)
        results.append(result)
    # The DOWN low/high must reproduce UP high/low, including full-window excursions.
    assert results[0].mfe == pytest.approx(results[1].mfe)
    assert results[0].mae == pytest.approx(results[1].mae)
    assert results[0].signed_return == pytest.approx(results[1].signed_return)


def test_primary_overlap_clock_does_not_connect_exact_seven_day_spacing():
    first = event()
    second = replace(first, event_id="second", data_cutoff=7 * DAY, decision_time=7 * DAY + LAG)
    assert len(interval_groups([first, second], 7 * DAY)) == 2
    assert len(interval_groups([first, second], 14 * DAY)) == 1


def test_crossing_dedup_and_causal_cooldown():
    rows = history(181) + [
        bar(181 * FOUR_HOURS, 110.0, interval=FOUR_HOURS),
        bar(182 * FOUR_HOURS, 111.0, interval=FOUR_HOURS),
    ]
    events, _ = candidates(rows)
    assert len(events) == 1
    e = event()
    items = [
        e,
        replace(e, event_id="b", decision_time=DAY + LAG, data_cutoff=DAY),
        replace(e, event_id="c", decision_time=14 * DAY + LAG, data_cutoff=14 * DAY),
    ]
    assert [e.event_id for e in spaced_events(items)] == ["e", "c"]
    assert len(interval_groups(items)) == 1
    assert fingerprint([e.event_id for e in spaced_events(items)]) == fingerprint(["e", "c"])


def test_purge_embargo_and_label_maturity():
    test = 30 * DAY
    safe = replace(event(), event_id="safe", decision_time=10 * DAY, data_cutoff=10 * DAY)
    overlap = replace(safe, event_id="overlap", decision_time=15 * DAY, data_cutoff=15 * DAY)
    near = replace(safe, event_id="near", decision_time=20 * DAY, data_cutoff=20 * DAY)
    base = label(event(), forward())
    labels = {
        "safe": replace(base, event_id="safe", label_end=17 * DAY, available_at=17 * DAY + LAG),
        "overlap": replace(base, event_id="overlap", label_end=test, available_at=test),
        "near": replace(base, event_id="near", label_end=27 * DAY, available_at=27 * DAY + LAG),
    }
    assert ResearchFold(test, 40 * DAY).training([safe, overlap, near], labels) == [safe]
    assert ResearchFold(test, 40 * DAY).testing([replace(safe, decision_time=test)])


def test_relative_volume_uses_immediately_preceding_174_bars():
    rows = [replace(b, volume=i + 1.0) for i, b in enumerate(history(181))]
    cutoff = rows[-1].end_time
    view = snapshot(rows, cutoff + LAG, cutoff)
    assert view.values["relative_volume"] == pytest.approx(178.5 / 88.5)


def test_invalid_label_geometry_fails_closed():
    with pytest.raises(ValueError):
        replace(event(), scale=0.0)
    with pytest.raises(ValueError):
        replace(event(), direction=0)
    with pytest.raises(ValueError):
        label(event(), forward(), upper=float("nan"))


def test_future_revision_conflicts_do_not_change_past_join():
    old = Observation("x", 1.0, 0, 5, 6, "src", "v1")
    future = Observation("x", 2.0, 0, 20, 21, "src", "v2")
    assert pit_join([old, future, replace(future, value=3.0)], 10) == pit_join([old], 10)
    with pytest.raises(ValueError, match="ambiguous revision"):
        pit_join([old, replace(old, value=2.0, vintage="unordered-name")], 10)
