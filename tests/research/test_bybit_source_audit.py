"""The source audit samples both survivors and ceased contracts before 2023."""

from research.futures.bybit_source_audit import (
    DAY_MS,
    matching_usdt_perpetuals,
    pick_sample,
    window_bounds,
)


def test_closed_query_must_exclude_unexpected_statuses():
    items = [{"symbol": symbol, "status": status,
              "contractType": "LinearPerpetual", "quoteCoin": "USDT"}
             for symbol, status in (("AUSDT", "Closed"), ("BUSDT", "PendingOpen"))]
    assert [item["symbol"] for item in matching_usdt_perpetuals(items, "Closed")] == ["AUSDT"]


def test_sample_keeps_closed_names_and_first_last_windows():
    contracts = [
        {"symbol": f"T{i}USDT", "status": "Trading", "launchTime": str((i + 1) * DAY_MS),
         "deliveryTime": "0"} for i in range(3)
    ] + [
        {"symbol": f"C{i}USDT", "status": "Closed", "launchTime": str((i + 1) * DAY_MS),
         "deliveryTime": str((i + 101) * DAY_MS + 1)} for i in range(3)
    ]
    sample = pick_sample(contracts, each=2)
    assert [item["symbol"] for item in sample] == ["T0USDT", "T1USDT", "C0USDT", "C1USDT"]
    assert window_bounds(sample[2], "first") == (DAY_MS, 31 * DAY_MS)
    assert window_bounds(sample[2], "last") == (72 * DAY_MS, 102 * DAY_MS)
