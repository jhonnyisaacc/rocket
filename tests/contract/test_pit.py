from datetime import UTC, datetime, timedelta

from rocket.pit import Availability, PointInTime

NOW = datetime(2026, 9, 7, 15, 0, tzinfo=UTC)


def test_missing_available_at_is_unknown_not_eligible():
    point = PointInTime(event_time=NOW - timedelta(days=1), decision_time=NOW)
    assert point.availability is Availability.UNKNOWN


def test_event_after_decision_is_late():
    point = PointInTime(
        event_time=NOW + timedelta(seconds=1),
        available_at=NOW + timedelta(seconds=1),
        decision_time=NOW,
    )
    assert point.availability is Availability.LATE


def test_available_after_decision_is_late():
    point = PointInTime(
        event_time=NOW - timedelta(minutes=1),
        available_at=NOW + timedelta(seconds=1),
        decision_time=NOW,
    )
    assert point.availability is Availability.LATE


def test_eligible_when_available_at_or_before_decision():
    point = PointInTime(
        event_time=NOW - timedelta(minutes=5),
        available_at=NOW - timedelta(minutes=1),
        decision_time=NOW,
    )
    assert point.availability is Availability.ELIGIBLE


def test_naive_timestamp_rejected():
    from datetime import datetime

    try:
        PointInTime(decision_time=datetime(2026, 9, 7, 15, 0))
    except ValueError as exc:
        assert "timezone" in str(exc)
    else:
        raise AssertionError("naive timestamps must fail")
