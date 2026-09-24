"""Monthly file inventory must keep funding and candles distinct."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "research/futures/archive_coverage.py"
SPEC = importlib.util.spec_from_file_location("archive_coverage", MODULE_PATH)
assert SPEC and SPEC.loader
archive_coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive_coverage)


def test_months_for_requires_matching_symbol_and_kind(monkeypatch):
    monkeypatch.setattr(archive_coverage, "list_keys", lambda prefix, timeout: [
        f"{prefix}OLDUSDT-1d-2021-01.zip",
        f"{prefix}OTHERUSDT-1d-2021-01.zip",
        f"{prefix}OLDUSDT-1d-2021-01.zip.CHECKSUM",
    ])
    assert archive_coverage.months_for("OLDUSDT", "klines") == ["2021-01"]


def test_months_for_rejects_unknown_kind():
    with pytest.raises(ValueError):
        archive_coverage.months_for("BTCUSDT", "spot")
