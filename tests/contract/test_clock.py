from datetime import UTC, datetime

from rocket.clock import equity_observation_fresh


def test_holiday_session_clock_does_not_refresh_stale_market_data():
    monday = datetime(2026, 9, 7, 18, tzinfo=UTC)
    assert equity_observation_fresh("2026-09-04T00:00:00Z", monday)
    assert equity_observation_fresh("2026-09-04T20:00:00Z", monday, daily=False)
    assert not equity_observation_fresh("2026-09-03T00:00:00Z", monday)
    assert not equity_observation_fresh("2026-09-04T20:00:00Z", datetime(2026, 9, 8, 15, tzinfo=UTC), daily=False)
    assert not equity_observation_fresh("2026-09-08T20:00:00Z", monday, daily=False)
