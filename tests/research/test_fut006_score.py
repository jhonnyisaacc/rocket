from datetime import UTC, date, datetime, timedelta

from research.futures.fut006_score import score_symbol


def test_delayed_proxy_accounting_reversal_funding_and_final_flatten():
    first = date(2024, 11, 1)
    windows = {}
    for index in range(62):
        day = first + timedelta(days=index)
        midnight = int(datetime(day.year, day.month, day.day,
                                tzinfo=UTC).timestamp() * 1000)
        for hour in (0, 12):
            clock = f"{hour:02d}:15"
            windows[(day.isoformat(), clock)] = {
                "buy_qty": 2.0 if (index * 2 + hour // 12) % 2 == 0 else 1.0,
                "sell_qty": 1.0 if (index * 2 + hour // 12) % 2 == 0 else 2.0,
                "signal_rows": 2,
                "proxy_price": 100.0,
                "proxy_ms": midnight + (hour * 60 + 15) * 60_000 + 20_000,
            }
    midnight = int(datetime(2024, 11, 1, tzinfo=UTC).timestamp() * 1000)
    funding = [(midnight + 8 * 3_600_000 * index,
                midnight + 8 * 3_600_000 * index, 8,
                0.0001 if index == 1 else 0.0)
               for index in range(184)]
    result = score_symbol("BTCUSDT", windows,
                          (funding, [row[0] for row in funding]))
    assert len(result) == 122
    assert result[0]["oi_sign"]["target"] == 1
    assert result[0]["oi_sign"]["turnover"] == 1
    assert abs(result[0]["oi_sign"]["net_5bp_side"] + 0.0006) < 1e-12
    assert result[1]["oi_sign"]["target"] == -1
    assert result[1]["oi_sign"]["turnover"] == 2
    assert abs(result[1]["oi_sign"]["net_5bp_side"] + 0.001) < 1e-12
    assert result[-1]["oi_sign"]["turnover"] == 3
