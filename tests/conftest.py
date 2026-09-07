from datetime import UTC, datetime

import pytest

NOW = datetime(2026, 9, 7, 15, 0, tzinfo=UTC)


@pytest.fixture
def now():
    return NOW
