from __future__ import annotations

from scripts.research.memecoin_fast_flow import leave_best_out


def test_best_winner_removal_exposes_negative_remainder():
    rows = [{"returns": {"155000": value}} for value in (2.0, -0.1, -0.2)]
    assert leave_best_out(rows, 155000) == -0.15000000000000002
    assert leave_best_out(rows[:1], 155000) is None
