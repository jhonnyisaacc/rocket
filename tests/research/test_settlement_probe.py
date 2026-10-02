"""Settlement probes preserve instrument identity and issue month."""

from research.futures.settlement_probe import issue_months, minute_key


def test_issue_months_deduplicates_components():
    day = 1744588800000  # 2025-04-14
    data = {"unresolved_exposures": [{"symbol": "BADGERUSDT", "entry_ms": day},
                                     {"symbol": "BADGERUSDT", "entry_ms": day}]}
    assert issue_months(data) == [("BADGERUSDT", "2025-04")]
    assert minute_key("BADGERUSDT", "2025-04", "indexPriceKlines").endswith(
        "/BADGERUSDT/1m/BADGERUSDT-1m-2025-04.zip")


def test_issue_on_first_day_includes_prior_month():
    day = 1746057600000  # 2025-05-01
    assert issue_months({"unresolved_exposures": [
        {"symbol": "ALPACAUSDT", "entry_ms": day}]}) == [
            ("ALPACAUSDT", "2025-04"), ("ALPACAUSDT", "2025-05")]
