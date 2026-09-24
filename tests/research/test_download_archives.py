"""Source archive identity and PIT-neutral task construction."""

from research.futures.download_archives import archive_key, tasks_from_coverage


def test_archive_paths_keep_native_symbol_and_data_kind():
    assert archive_key("LUNAUSDT", "klines", "2022-05").endswith(
        "/LUNAUSDT/1d/LUNAUSDT-1d-2022-05.zip"
    )
    assert archive_key("LUNAUSDT", "fundingRate", "2022-05").endswith(
        "/LUNAUSDT/LUNAUSDT-fundingRate-2022-05.zip"
    )
    assert "币安人生USDT" in archive_key("币安人生USDT", "klines", "2025-10")


def test_tasks_keep_delisted_name_and_future_month_out_of_window():
    coverage = {"symbols": {"LUNAUSDT": {
        "klines": ["2022-05", "2026-01"], "fundingRate": ["2022-05"]}}}
    assert tasks_from_coverage(coverage, 2022, 2025) == [
        ("LUNAUSDT", "klines", "2022-05"),
        ("LUNAUSDT", "fundingRate", "2022-05"),
    ]
