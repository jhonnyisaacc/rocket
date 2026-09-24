from datetime import UTC, date, datetime

from research.futures.fut005_cot_score import daily_targets, score_day


def test_report_is_unusable_until_publication_and_expires_when_stale():
    rows = [{"asof": date(2025, 9, 30), "available": date(2025, 11, 20),
             "delta": 0.1}]
    assert daily_targets(rows, {}, date(2025, 10, 10))["cot_change"] == 0
    assert daily_targets(rows, {}, date(2025, 11, 20))["cot_change"] == 0


def test_fresh_report_sets_paper_signed_direction_independently_of_price():
    day = date(2024, 1, 12)
    start = int(datetime(2024, 1, 12, tzinfo=UTC).timestamp() * 1000)
    rows = [{"asof": date(2024, 1, 2), "available": day, "delta": -0.1}]
    prices = {start - 86_400_000: (100.0, 100.0),
              start - 8 * 86_400_000: (90.0, 90.0)}
    assert daily_targets(rows, prices, day) == {
        "cot_change": -1, "always_long": 1, "price_7d": 1}


def test_reversal_and_terminal_exit_both_charge_turnover():
    day = date(2024, 12, 31)
    start = int(datetime(2024, 12, 31, tzinfo=UTC).timestamp() * 1000)
    hour = 3_600_000
    funding = [(start - 8 * hour, start - 8 * hour, 8, 0.0),
               (start, start, 8, 0.0),
               (start + 8 * hour, start + 8 * hour, 8, 0.0001),
               (start + 16 * hour, start + 16 * hour, 8, 0.0001),
               (start + 24 * hour, start + 24 * hour, 8, 0.0001)]
    targets = {"cot_change": 1, "always_long": 1, "price_7d": 1}
    previous = {"cot_change": -1, "always_long": 0, "price_7d": 0}
    result = score_day(day, targets, previous,
                       {start: (100.0, 100.0), start + 24 * hour: (101.0, 101.0)},
                       funding, [row[0] for row in funding], terminal=True)
    assert result["cot_change"]["turnover"] == 3
    assert abs(result["cot_change"]["net_20bps"] - 0.0067) < 1e-12
