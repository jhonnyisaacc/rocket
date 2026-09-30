import httpx
import pytest

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
    assert factors["earnings_revision_deterioration"] is None  # Different periods are not forecast revisions.


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


def test_chamber_latest_uses_plan_ceiling():
    seen = []

    def handler(request):
        seen.append((request.url.path, request.url.params.get("page"), request.url.params.get("limit")))
        return httpx.Response(200, json=[{
            "firstName": "Jane", "lastName": "Doe", "symbol": "AAPL", "type": "Purchase",
            "transactionDate": "2026-08-01", "disclosureDate": "2026-08-10", "link": "https://example.test/a",
        }])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = FMPClient(api_key="test", http=client).politician_trades()
    assert result.status is OperationalStatus.HEALTHY
    assert len(result.records) == 2
    assert seen == [
        ("/stable/house-latest", "0", "25"),
        ("/stable/senate-latest", "0", "25"),
    ]


def test_chamber_latest_402_is_entitlement():
    def handler(request):
        return httpx.Response(402, json={"Error": "Payment Required"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = FMPClient(api_key="test", http=client).politician_trades()
    assert result.status is OperationalStatus.UNAVAILABLE
    assert result.failure_kind == "Entitlement"
    assert result.extras["page"] == 0
    assert result.extras["limit"] == 25
    assert not result.records


@pytest.mark.parametrize("code,kind", [(402, "Entitlement"), (429, "RateLimit")])
def test_pelosi_person_history_reports_entitlement_or_rate_limit(code, kind):
    def handler(request):
        return httpx.Response(code, json={"Error": "blocked"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = FMPClient(api_key="test", http=client).person_history()
    assert result.status is OperationalStatus.UNAVAILABLE
    assert result.failure_kind == kind
    assert not result.records


def test_missing_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    result = FMPClient(api_key="").fundamentals("AAPL")
    assert result.status is OperationalStatus.UNAVAILABLE
    assert result.failure_kind == "NO_SETUP"
