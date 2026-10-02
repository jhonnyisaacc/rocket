from datetime import date

from research.futures.cftc_cot_source_audit import available_date


def test_ordinary_report_cannot_trade_asof_or_release_friday():
    assert available_date(date(2024, 1, 2)) == date(2024, 1, 12)


def test_ion_delay_overrides_normal_release_lag():
    assert available_date(date(2023, 1, 31)) == date(2023, 2, 25)


def test_shutdown_delay_uses_amended_cftc_schedule():
    assert available_date(date(2025, 9, 30)) == date(2025, 11, 20)
    assert available_date(date(2025, 11, 18)) == date(2025, 12, 13)
