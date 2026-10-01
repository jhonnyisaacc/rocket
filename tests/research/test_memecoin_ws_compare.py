from __future__ import annotations

from scripts.research.memecoin_ws_compare import summary


def test_paired_receipt_summary_keeps_signed_differences():
    values = [-6.0, -1.0, 0.0, 2.0, 7.0]
    result = summary(values)
    assert result["median"] == 0
    assert result["min"] == -6
    assert result["max"] == 7
