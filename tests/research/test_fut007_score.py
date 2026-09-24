from datetime import UTC, date, datetime, timedelta

from research.futures.fut007_score import funding_rank, score_partition


def test_midrank_handles_ties_without_using_current_observation():
    assert funding_rank(-1.0, [0.0] * 300) == 0.0
    assert funding_rank(0.0, [0.0] * 300) == 0.5


def test_delayed_funding_signal_charges_actual_payment_and_flatten():
    start = date(2023, 7, 1)
    end = start + timedelta(days=2)
    first_slot = int(datetime(2023, 1, 2, tzinfo=UTC).timestamp() * 1000)
    last_slot = int(datetime(2023, 7, 3, tzinfo=UTC).timestamp() * 1000)
    hour = 3_600_000
    funding = []
    for stamp in range(first_slot, last_slot + 1, 8 * hour):
        rate = (-0.01 if stamp == int(datetime(2023, 7, 1, tzinfo=UTC).timestamp() * 1000)
                else 0.0001 if stamp == int(datetime(2023, 7, 1, 8, tzinfo=UTC).timestamp() * 1000)
                else 0.0)
        funding.append((stamp, stamp + 15, 8, rate))
    prices = {}
    for day, opening in ((start, 100.0),
                         (start + timedelta(days=1), 101.0),
                         (end, 102.0)):
        midnight = int(datetime(day.year, day.month, day.day,
                                tzinfo=UTC).timestamp() * 1000)
        prices[midnight + hour] = (opening, opening)
        prices[midnight - hour] = (opening, opening)
        prices[midnight - 5 * hour] = (opening, opening)
    result = score_partition(start, end, prices, funding,
                             [row[0] for row in funding])
    assert len(result) == 2
    assert result[0]["lower_tail"]["target"] == 1
    assert result[1]["lower_tail"]["target"] == 0
    assert result[0]["lower_tail"]["turnover"] == 1
    assert result[1]["lower_tail"]["turnover"] == 1
    assert abs(result[0]["lower_tail"]["net_5bp_side"] - 0.0094) < 1e-12
    assert abs(result[1]["lower_tail"]["net_5bp_side"] + 0.0005) < 1e-12
