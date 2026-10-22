"""Frozen momentum-event contract v1: single source of truth for parameters.

Mirrors docs/research/momentum/MOMENTUM_EVENT_CONTRACT.md (freeze
2026-10-02). Import these constants; never re-declare the numbers
elsewhere. Any change requires a contract version bump plus a recorded
pre-result amendment.
"""

from __future__ import annotations

CANDIDATE_GENERATOR_VERSION = "candgen-v1"
LABEL_CONTRACT_VERSION = "label-v1"
FEATURE_SCHEMA_VERSION = "feat-v1"
MODEL_VERSION = "m1-logreg-c1"
CENSUS_VERSION = "mom000-v1"

# Clocks (all UTC).
BAR_4H_SECONDS = 4 * 3600
BAR_1H_SECONDS = 3600
DECISION_LAG_SECONDS = 5 * 60  # decision_time = cutoff + 5m.
HISTORY_DAYS_REQUIRED = 30  # contiguous 4h history required, else UNKNOWN.

# Candidate generator (log-price, volatility-normalized Donchian crossing).
SIGMA_BARS = 180  # sample SD over last 180 4h log-close returns.
LOOKBACK_BARS = 42  # highest high / lowest low window (preceding bars).
BREAK_PCT_SIGMA = 0.5  # close must clear the extreme by >= 0.5 sigma.
COOLDOWN_SECONDS = 14 * 24 * 3600  # global 14d cooldown, either side.

# Forward label (triple barrier, diffusion-scaled).
HORIZON_PRIMARY_DAYS = 7
HORIZON_SENSITIVITY_DAYS = (3, 14)
UPPER_MULT = 2.0  # favorable barrier: direction*log(P/P0) >= 2S.
LOWER_MULT = 1.0  # adverse barrier: direction*log(P/P0) <= -1S.
SENSITIVITY_BARRIERS = ((2.0, 1.0), (1.6, 1.0), (2.4, 1.0), (2.0, 0.8), (2.0, 1.2))

# Folds / embargo / budget.
MIN_TRAIN_MONTHS = 24
EMBARGO_SECONDS = COOLDOWN_SECONDS  # 14d pre-test embargo.
ALERT_BUDGET_FRAC = 0.25  # floor(25% of annual independent candidates).
NULL_SHIFTS = 1000

# Costs (round-trip hurdles for the economic sanity check only).
COST_HURDLES_BP = (20.0, 40.0, 80.0)

DIRECTIONS = ("UP", "DOWN")
OUTCOMES = ("CONTINUES", "FAILS", "TIMEOUT", "UNKNOWN")

__all__ = [name for name in dir() if not name.startswith("_")]
