from __future__ import annotations

import math

import pytest

from scripts.research.memecoin_flow_diagnostics import (
    exact_binomial_interval,
    fisher_lower_tail,
)


def test_exact_binomial_interval_does_not_treat_zero_observed_risk_as_zero_true_risk():
    lower, upper = exact_binomial_interval(0, 11)
    assert lower == 0
    assert upper == pytest.approx(1 - 0.025 ** (1 / 11))


def test_fisher_tail_uses_disjoint_top_and_rest_counts():
    assert fisher_lower_tail(0, 2, 2, 2) == pytest.approx(1 / math.comb(4, 2))
    assert fisher_lower_tail(0, 0, 2, 2) is None
