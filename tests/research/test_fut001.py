"""FUT-001 causal boundaries and funding treatment."""

from research.futures.fut001 import DAY_MS, HOUR_MS, forecast, funding_window, score


def test_forecast_uses_completed_closes_only():
    prices = [100 * 1.001**i for i in range(121)]
    value, control = forecast(prices, 0.5)
    assert 0 < value <= 1
    assert 0 < control <= 1
    assert forecast(prices, 0.5) == (value, control)


def test_funding_includes_print_after_entry_open_and_detects_gap():
    start = 1_700_006_400_000  # arbitrary hour-aligned epoch millisecond
    start -= start % HOUR_MS
    records = [(start, start + 14, 8, 0.001),
               (start + 8 * HOUR_MS, start + 8 * HOUR_MS + 14, 8, 0.002),
               (start + 16 * HOUR_MS, start + 16 * HOUR_MS + 14, 8, 0.003)]
    slots = [row[0] for row in records]
    assert funding_window(records, slots, start, start + DAY_MS) == (True, 0.006)
    assert funding_window(records[:2], slots[:2], start, start + DAY_MS)[0] is False


def test_missing_exposed_exit_blocks_positive_verdict():
    day = 1_735_689_600_000  # 2025-01-01 UTC
    signals = {day: {"X": {"multi": 1.0, "single": 1.0, "vol": 1.0,
                            "return": None, "funding": None,
                            "unresolved": ["missing_or_inactive_exit"]}}}
    result = score(signals, {day: {"X": True}}, component="multi", bps=20)
    assert result["unresolved_exposures"][0]["symbol"] == "X"
