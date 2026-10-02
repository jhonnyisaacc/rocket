"""Archive normalization preserves adverse and inactive historical rows."""

from __future__ import annotations

import io
import zipfile

import pytest

from research.futures.normalize_archives import parse_funding, parse_prices


def zipped(name: str, contents: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(name, contents)
    return output.getvalue()


def test_flat_zero_volume_bar_is_retained_but_ineligible():
    raw = zipped("x.csv", "1640995200000,1,1,1,1,0,1641081599999,0,0,0,0,0\n")
    assert parse_prices(raw)[0][-1] == 0


def test_missing_or_incorrect_daily_boundary_is_rejected():
    raw = zipped("x.csv", "1640995200000,1,2,1,2,1,1641081600000,2,1,0,0,0\n")
    with pytest.raises(ValueError, match="timestamp"):
        parse_prices(raw)


def test_funding_keeps_actual_stamp_and_hour_slot():
    raw = zipped("x.csv", "calc_time,funding_interval_hours,last_funding_rate\n"
                        "1641024000014,8,0.0001\n")
    assert parse_funding(raw) == [(1641024000000, 1641024000014, 8, 0.0001)]
