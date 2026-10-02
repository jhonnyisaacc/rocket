from __future__ import annotations

import pytest

from research.futures.fut004_gross import settlement_price


def test_settlement_stress_is_adverse_for_each_side() -> None:
    event = {"cutoff_sensitivity_mean_low": 90.0,
             "approx_index_settlement_price": 100.0,
             "cutoff_sensitivity_mean_high": 110.0}
    assert [settlement_price(event, 0.1, name) for name in (
        "adverse_stress", "adverse", "mid", "favorable", "favorable_stress")
    ] == pytest.approx([85.5, 90, 100, 110, 115.5])
    assert [settlement_price(event, -0.1, name) for name in (
        "adverse_stress", "adverse", "mid", "favorable", "favorable_stress")
    ] == pytest.approx([115.5, 110, 100, 90, 85.5])
