"""Walk-forward folds: expanding annual test years after >= 24m training.

Purge: drop any train example whose label interval [cutoff, cutoff+h]
overlaps the test span. Embargo: drop train examples with decision_time
within 14d before the test span starts. Test span for year Y is
[Y-01-01, Y+1-01-01); horizon spillover past year-end stays in test
(labels resolve with future bars; availability recorded separately).
"""

from __future__ import annotations

from datetime import UTC, datetime

from rocket.momentum import contracts

_YEAR_MS = 365 * 24 * 3600 * 1000  # nominal; spans use exact calendar below.


def _year_start_ms(year: int) -> int:
    return int(datetime(year, 1, 1, tzinfo=UTC).timestamp() * 1000)


def build_folds(
    events: list[dict],
    *,
    horizon_days: int = contracts.HORIZON_PRIMARY_DAYS,
    min_train_months: int = contracts.MIN_TRAIN_MONTHS,
) -> list[dict]:
    """Expanding folds. First test year = first year with >= min_train_months
    of preceding history. Folds with < 10 training events are skipped."""
    if not events:
        return []
    horizon_ms = horizon_days * 24 * 3600 * 1000
    embargo_ms = contracts.EMBARGO_SECONDS * 1000
    first_ms = min(e["cutoff_ms"] for e in events)
    first_year = datetime.fromtimestamp(first_ms / 1000, UTC).year
    last_year = datetime.fromtimestamp(max(e["cutoff_ms"] for e in events) / 1000, UTC).year
    train_start = first_ms
    folds = []
    for year in range(first_year, last_year + 1):
        test_start = _year_start_ms(year)
        test_end = _year_start_ms(year + 1)
        months_before = (test_start - first_ms) / (30.44 * 24 * 3600 * 1000)
        if months_before < min_train_months:
            continue
        train, test = [], []
        for e in events:
            c = e["cutoff_ms"]
            if test_start <= c < test_end:
                test.append(e)
            elif train_start <= c < test_start - embargo_ms:
                if c + horizon_ms < test_start:  # purge label-interval overlap.
                    train.append(e)
        if len(train) < 10 or not test:
            continue
        folds.append(
            {
                "test_year": year,
                "test_start_ms": test_start,
                "test_end_ms": test_end,
                "train": train,
                "test": test,
                "horizon_days": horizon_days,
            }
        )
    return folds
