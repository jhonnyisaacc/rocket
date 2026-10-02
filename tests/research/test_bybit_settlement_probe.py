"""Minute index envelopes exclude the cutoff minute."""

from research.futures.bybit_settlement_probe import MINUTE_MS, mean_envelope


def test_30_minute_envelope_uses_pre_cutoff_minutes_only():
    cutoff = 60 * MINUTE_MS
    rows = {cutoff - step * MINUTE_MS: ["0", "1", "3", "1", "2"]
            for step in range(1, 31)}
    rows[cutoff] = ["0", "100", "100", "100", "100"]
    assert mean_envelope(rows, cutoff, 30) == {
        "mean_low": 1.0, "mean_close": 2.0, "mean_high": 3.0}
    assert mean_envelope(rows, cutoff, 60) is None
