from rocket.models import OperationalStatus
from rocket.providers.fmp import FMPClient, map_short_factors, parse_politician_row


def test_map_short_factors_bearish_growth_and_cheap_pe():
    factors = map_short_factors(
        {
            "profile": [{"eps": 2.0, "pe": 40}],
            "ratios_ttm": [{"peRatioTTM": 12.0}],
            "analyst_estimates": [
                {"estimatedEpsAvg": 1.0},
                {"estimatedEpsAvg": 1.5},
            ],
        }
    )
    assert factors["company_fundamentals"] is True
    assert factors["valuation_support"] is True
    assert factors["earnings_revision_deterioration"] is True


def test_map_short_factors_missing_stays_none():
    factors = map_short_factors({"profile": {}, "ratios_ttm": {}, "analyst_estimates": []})
    assert factors["company_fundamentals"] is None
    assert factors["valuation_support"] is None
    assert factors["earnings_revision_deterioration"] is None


def test_politician_row_keeps_source_link():
    row = parse_politician_row(
        "senate",
        {
            "firstName": "Jane",
            "lastName": "Doe",
            "symbol": "AAPL",
            "type": "Purchase",
            "transactionDate": "2026-08-01",
            "disclosureDate": "2026-08-10",
            "link": "https://efdsearch.senate.gov/x",
        },
    )
    assert row["subject"] == "Jane Doe"
    assert row["provider"] == "fmp"
    assert row["source_url"] == "https://efdsearch.senate.gov/x"


def test_missing_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    result = FMPClient(api_key="").fundamentals("AAPL")
    assert result.status is OperationalStatus.UNAVAILABLE
    assert result.failure_kind == "NO_SETUP"
