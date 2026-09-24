"""The Bybit preflight uses only observed history for eligibility."""

from research.futures.bybit_eligibility import START, parse_prices, preflight_symbol
from research.futures.bybit_source_audit import DAY_MS


def test_anomalous_first_bar_is_retained_but_not_tradable():
    bars, anomalies = parse_prices([
        [str(START), "0", "10", "0", "9", "100", "900"],
        [str(START + DAY_MS), "9", "10", "8", "9.5", "100", "950"],
    ])
    assert anomalies == [START]
    assert bars[START] == (900, False)
    assert bars[START + DAY_MS] == (950, True)


def test_preflight_does_not_require_future_fill_to_grant_prior_eligibility():
    bars = {START - step * DAY_MS: (10_000_000, True) for step in range(1, 122)}
    bars[START] = (10_000_000, True)
    first_funding = START - 31 * DAY_MS
    funding = [(stamp, stamp, 8, 0.0001)
               for stamp in range(first_funding, START + 2 * DAY_MS + 1, 8 * 3_600_000)]
    counts, issues = preflight_symbol("TESTUSDT", bars, funding)
    assert counts["eligible_symbol_days"] >= 1
    assert {issue["entry_ms"] for issue in issues} >= {START}
    assert any("missing_or_inactive_exit" in issue["reasons"] for issue in issues)
