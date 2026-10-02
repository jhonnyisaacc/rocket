"""Bybit's exceptional LUNA settlement must not use a generic index average."""

from research.futures.bybit_fut003_candidates import build


def test_special_luna_price_and_union_for_other_events():
    events = []
    for symbol, cutoff in (("LUNAUSDT", 1_652_349_780_000),
                           ("FTTUSDT", 1_668_340_800_000),
                           ("SRMUSDT", 1_668_481_200_000)):
        events.append({"symbol": symbol, "reported_delivery_ms": cutoff,
                       "last_active_trade_minute_ms": cutoff - 60_000,
                       "index_at_cutoff": [str(cutoff), "0.024", "0.024", "0.024", "0.024"],
                       "index_30m": {"mean_low": 1.8, "mean_close": 2.0, "mean_high": 2.2},
                       "index_60m": {"mean_low": 1.7, "mean_close": 1.9, "mean_high": 2.1},
                       "sources": {"trade": {"sha256": "trade"},
                                   "index": {"sha256": "index"}}})
    candidates = {item["symbol"]: item for item in build({"events": events})}
    assert candidates["LUNAUSDT"]["approx_index_settlement_price"] == 0.024
    assert candidates["LUNAUSDT"]["cutoff_sensitivity_mean_low"] == 0.024
    assert candidates["FTTUSDT"]["cutoff_sensitivity_mean_low"] == 1.7
    assert candidates["FTTUSDT"]["approx_index_settlement_price"] == 2.0
    assert candidates["FTTUSDT"]["cutoff_sensitivity_mean_high"] == 2.2
