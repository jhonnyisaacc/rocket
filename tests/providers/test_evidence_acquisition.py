from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import httpx
import pytest

from rocket.models import OperationalStatus as O
from rocket.models import ResearchStatus as S
from rocket.providers.fmp import FMPClient, map_short_factors
from rocket.providers.fred import fetch_series
from rocket.providers.http import get_read
from rocket.providers.quotes import acquire_quotes
from rocket.providers.shorts import acquire_short_snapshot
from rocket.providers.supadata import SupadataTranscriptProvider, Transcript, TranscriptUnavailable
from rocket.store import ResearchStore
from rocket.workflows.cava import CavaWorkflow, corroborate_claims
from rocket.workflows.macro import MacroWorkflow
from tests.workflows.test_cava import NOW, RSS, FixtureTranscript


def response(code=200, payload=None):
    return httpx.Response(code, json=payload, request=httpx.Request("GET", "https://provider.test"))


@pytest.mark.parametrize("first", [429, 500, 502, 503, 504, "timeout"])
def test_bounded_read_retry_success(first):
    http = Mock()
    http.get.side_effect = [httpx.ReadTimeout("timeout") if first == "timeout" else response(first), response(200, {"ok": True})]
    assert get_read(http, "https://provider.test").json() == {"ok": True}
    assert http.get.call_count == 2


def test_credential_error_is_not_retried():
    http = Mock()
    http.get.return_value = response(401)
    with pytest.raises(httpx.HTTPStatusError):
        get_read(http, "https://provider.test")
    assert http.get.call_count == 1


def test_retry_is_bounded():
    http = Mock()
    http.get.return_value = response(503)
    with pytest.raises(httpx.HTTPStatusError):
        get_read(http, "https://provider.test")
    assert http.get.call_count == 2


@pytest.mark.parametrize("primary", [{"records": []}, {"records": [{"date": "2026-09-01", "value": "."}]}])
def test_fred_fallback_on_unusable_openbb(monkeypatch, primary):
    from rocket.providers import fred
    monkeypatch.setattr(fred, "fetch_openbb_fred", lambda symbol: primary)
    fallback = Mock(return_value={"records": [{"date": "2026-09-01", "value": 1}], "source": "FRED direct"})
    monkeypatch.setattr(fred, "fetch_fred_csv", fallback)
    data, source = fetch_series("EFFR")
    assert source == "FRED direct" and data["records"]
    fallback.assert_called_once()


def test_fmp_retains_ratios_when_estimates_fail_and_acquires_growth():
    requests = []
    def handler(req):
        requests.append(req.url.path)
        if req.url.path.endswith("profile"):
            return httpx.Response(200, json=[{"symbol": "AAPL"}])
        if req.url.path.endswith("ratios-ttm"):
            return httpx.Response(200, json=[{"priceToEarningsRatioTTM": 30}])
        if req.url.path.endswith("analyst-estimates"):
            return httpx.Response(403, json={"Error": "not entitled"})
        assert req.url.path.endswith("income-statement-growth")
        return httpx.Response(200, json=[{"symbol": "AAPL", "date": "2026-06-30", "growthEPS": -0.2}])
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = FMPClient(api_key="test", http=client).fundamentals("AAPL")
    assert result.status is O.PARTIAL
    row = result.records[0]
    assert row["pe_ttm"] == 30
    assert row["company_fundamentals"] is True
    assert row["eps_growth_basis"] == "reported annual EPS growth"
    assert row["earnings_revision_deterioration"] is None
    assert len(requests) == 4
    assert any(p["name"] == "fmp:analyst_estimates" and p["status"] == "UNAVAILABLE" for p in row["provider_attempts"])


def test_fmp_stable_eps_field_and_periods_not_revisions():
    row = map_short_factors({"profile": [{"eps": 2}], "analyst_estimates": [{"epsAvg": 1}, {"epsAvg": 3}]})
    assert row["company_fundamentals"] is True
    assert row["earnings_revision_deterioration"] is None


def test_yahoo_watch_supported_host_fallback_and_normalization():
    calls = []
    now = datetime(2026, 9, 8, 15, tzinfo=UTC)
    def handler(req):
        calls.append(req.url.host)
        if req.url.host.startswith("query2"):
            return httpx.Response(503)
        return httpx.Response(200, json={"chart": {"result": [{"meta": {
            "symbol": "CAT", "instrumentType": "EQUITY", "regularMarketTime": int(now.timestamp()), "regularMarketPrice": 101}}]}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = acquire_quotes([{"ticker": " cat "}], now=now, client=client)
    assert calls == ["query2.finance.yahoo.com", "query1.finance.yahoo.com"]
    assert rows["CAT"]["status"] == "OK"
    assert rows["CAT"]["available_at"] == now.isoformat()


def test_short_history_fallback_and_partial_fundamentals():
    calls = []
    def handler(req):
        calls.append((req.url.host, req.url.path))
        if req.url.host.startswith("query2"):
            return httpx.Response(503)
        return httpx.Response(200, json={"chart": {"result": [{"meta": {"regularMarketTime": int(NOW.timestamp())},
                        "indicators": {"quote": [{"close": list(range(80, 110))}]}}]}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = acquire_short_snapshot(now=NOW, universe={"AAPL": "XLK"}, http=client,
                                      fundamentals=lambda ticker: {"company_fundamentals": False})
    assert len(calls) == 6
    assert rows[0]["technical_breakdown"] is False
    assert rows[0]["company_fundamentals"] is False
    assert rows[0]["catalyst"] is None


def test_supadata_bounded_job_poll_and_no_secret_in_errors():
    http = Mock()
    http.get.side_effect = [response(200, {"jobId": "job"}), response(200, {"status": "queued"}), response(200, {"content": "Transcript"})]
    provider = SupadataTranscriptProvider(api_key="not-for-output", http=http, sleeper=lambda seconds: None, clock=lambda: NOW)
    assert provider.fetch("video").text == "Transcript"
    assert http.get.call_count == 3
    http.get.side_effect = None
    http.get.return_value = response(401)
    with pytest.raises(TranscriptUnavailable) as exc:
        provider.fetch("video")
    assert "not-for-output" not in str(exc.value)
    assert "https:" not in str(exc.value)


class AdvancingClock(datetime):
    calls = 0
    @classmethod
    def now(cls, tz=None):
        cls.calls += 1
        return NOW + timedelta(seconds=cls.calls * 10)


def test_cava_decides_after_transcript_and_corroboration(monkeypatch, tmp_path):
    from rocket.workflows import cava
    AdvancingClock.calls = 0
    monkeypatch.setattr(cava, "datetime", AdvancingClock)
    provider = FixtureTranscript(Transcript("Las tasas de la Fed importan.", "es", "supadata", NOW + timedelta(seconds=15)))
    def corroborate(video, claims, decided):
        return corroborate_claims(claims, decided, series_fetcher=lambda symbol: {
            "records": [{"date": "2026-09-01", "value": 3}], "retrieved_at": (NOW + timedelta(seconds=25)).isoformat()})
    result = CavaWorkflow(store=ResearchStore(tmp_path)).run(rss_xml=RSS, transcript_provider=provider, corroborate=corroborate)
    assert result.status is S.SETUP_FOUND
    assert result.started_at < result.decision_time
    assert all(e.availability.value == "ELIGIBLE" for e in result.evidence)
    assert result.payload["cursor_advanced"]


def test_macro_decision_clock_after_acquisition(monkeypatch):
    from rocket.workflows import macro
    AdvancingClock.calls = 0
    monkeypatch.setattr(macro, "datetime", AdvancingClock)
    def fetch(symbol):
        return {"records": [{"date": "2026-08-01", "value": 10}, {"date": "2026-09-04", "value": 10}],
                "retrieved_at": (NOW + timedelta(seconds=15)).isoformat()}, "fixture"
    result = MacroWorkflow(fetcher=fetch).run()
    assert result.status is S.NO_SETUP
    assert result.started_at < result.decision_time
    assert all(e.availability.value == "ELIGIBLE" for e in result.evidence)


def test_fred_short_primary_history_attempts_csv(monkeypatch):
    from rocket.providers import fred
    monkeypatch.setattr(fred, "fetch_openbb_fred", lambda symbol: {"records": [{"date": "2026-09-04", "value": 3}]})
    fallback = Mock(return_value={"records": [{"date": "2026-08-01", "value": 3}, {"date": "2026-09-04", "value": 3}], "source": "FRED direct"})
    monkeypatch.setattr(fred, "fetch_fred_csv", fallback)
    assert fetch_series("EFFR", minimum_history_days=28)[1] == "FRED direct"
    fallback.assert_called_once()


def test_ism_url_cannot_supply_headline_when_body_is_unavailable():
    from rocket.providers.ism import parse_ism_html
    report = parse_ism_html("<html>Access unavailable</html>", kind="manufacturing",
                            source_url="https://www.prnewswire.com/news-releases/manufacturing-pmi-at-54-6-august-2026-report.html")
    assert report.pmi is None
    assert not report.expanding


def test_ism_publisher_failure_retains_independent_official_roundup():
    from rocket.providers.ism import fetch_ism_report
    roundup = "https://www.ismworld.org/blog/2026/ism-pmi-reports-roundup-august-2026-services/"
    release = "https://www.prnewswire.com/news-releases/services-pmi-at-55-4-august-2026-report.html"
    def handler(req):
        if req.url.path.endswith("sitemap.xml"):
            return httpx.Response(200, text=f"<loc>{roundup}</loc>")
        if req.url.host == "www.ismworld.org":
            return httpx.Response(200, text=f'<h1>August 2026 Services</h1>Services PMI registered 55.4 percent. <a href="{release}">full report</a>')
        return httpx.Response(503)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = fetch_ism_report("services", http=client)
    assert report.pmi == 55.4
    assert report.source_url == roundup
    assert not report.expanding
