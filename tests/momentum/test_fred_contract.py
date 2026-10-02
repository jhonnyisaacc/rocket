from datetime import UTC, datetime

import httpx

from rocket.providers.fred import FredMacroSeries, fetch_fred_csv


def test_normal_fred_csv_is_explicitly_not_a_historical_vintage():
    def handler(request):
        assert "realtime_start" not in request.url.params
        return httpx.Response(200, text="DATE,WALCL\n2020-01-01,100\n")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_fred_csv("WALCL", http=client)
    assert result["history_mode"] == "CURRENT_REPORTED_HISTORY"
    assert result["historical_pit"] is False
    assert result["available_at"] is None
    assert result["vintage_id"] is None
    assert result["retrieved_at"]


def test_fred_adapter_exposes_unknown_release_not_observation_availability():
    provider = FredMacroSeries(
        fetcher=lambda symbol: (
            {
                "records": [{"date": "2020-01-01", "WALCL": 100}],
                "retrieved_at": "2026-10-02T20:00:00Z",
            },
            "fixture",
        )
    )
    result = provider.fetch("WALCL", now=datetime(2026, 10, 2, tzinfo=UTC))
    assert result.extras["historical_pit"] is False
    assert result.extras["available_at"] is None
    assert result.extras["vintage_id"] is None
