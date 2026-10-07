"""Recorded Senate eFD fixtures. Acquisition uses MockTransport, never the live site."""

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from rocket.providers.disclosures import HOUSE_FILING_YEAR_LOOKBACK
from rocket.providers.senate_efd import (
    SENATE_EFD_DATA_URL,
    SENATE_EFD_HOME_URL,
    SENATE_EFD_PTR_PAUSE,
    SENATE_EFD_PTR_TYPE_ID,
    SENATE_EFD_SEARCH_URL,
    OfficialSenateEFDProvider,
    submitted_window,
)

FIXTURES = Path(__file__).parent / "fixtures" / "senate_efd"
HOME = (FIXTURES / "home.html").read_text(encoding="utf-8")
DATA = json.loads((FIXTURES / "data.json").read_text(encoding="utf-8"))
PTR = (FIXTURES / "ptr.html").read_text(encoding="utf-8")
AKAMAI = (FIXTURES / "akamai_403.html").read_text(encoding="utf-8")
NOW = datetime(2026, 10, 7, tzinfo=UTC)
PTR_URL = "https://efdsearch.senate.gov/search/view/ptr/11111111-1111-1111-1111-111111111111/"
AMENDMENT_URL = "https://efdsearch.senate.gov/search/view/ptr/22222222-2222-2222-2222-222222222222/"
PAPER_URL = "https://efdsearch.senate.gov/search/view/paper/33333333-3333-3333-3333-333333333333/"


def test_default_lookback_matches_house_filing_years():
    start, end = submitted_window(NOW, HOUSE_FILING_YEAR_LOOKBACK)
    assert HOUSE_FILING_YEAR_LOOKBACK == 3
    assert list(range(NOW.year, NOW.year - HOUSE_FILING_YEAR_LOOKBACK, -1)) == [2026, 2025, 2024]
    assert start == "01/01/2024 00:00:00"
    assert end == "10/07/2026 23:59:59"


def _handler(calls, *, data_status=200, data_body=None, home_status=200, fail_data_times=0):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path == "/search/home/" and request.method == "GET":
            return httpx.Response(
                home_status,
                text=HOME if home_status == 200 else AKAMAI,
                headers={"set-cookie": "csrftoken=fixture-token; Path=/"},
            )
        if path == "/search/home/" and request.method == "POST":
            return httpx.Response(200, text="ok")
        if path == "/search/report/data/":
            data_calls = sum(1 for item in calls if item.url.path == "/search/report/data/")
            if data_calls <= fail_data_times:
                return httpx.Response(503, text="unavailable")
            if data_status != 200:
                body = AKAMAI if data_status == 403 else "limit"
                return httpx.Response(data_status, text=body)
            return httpx.Response(200, json=DATA if data_body is None else data_body)
        if path.startswith("/search/view/ptr/"):
            return httpx.Response(200, text=PTR)
        return httpx.Response(404, text="missing")

    return handler


def _fetch(handler, sleeps, **kwargs):
    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        return OfficialSenateEFDProvider(
            http=client,
            now=NOW,
            sleep=sleeps.append,
            **kwargs,
        ).fetch()


def test_agreement_and_ptr_rows_use_recorded_fixtures():
    calls = []
    sleeps = []
    result = _fetch(_handler(calls), sleeps)
    assert result.status == "HEALTHY"
    home_posts = [call for call in calls if call.method == "POST" and call.url.path == "/search/home/"]
    data_posts = [call for call in calls if call.url.path == "/search/report/data/"]
    assert len(home_posts) == 1
    body = parse_qs(home_posts[0].content.decode())
    assert body["csrfmiddlewaretoken"] == ["fixture-token"]
    assert body["prohibition_agreement"] == ["1"]
    assert home_posts[0].headers["referer"] == SENATE_EFD_HOME_URL
    assert len(data_posts) == 1
    data = parse_qs(data_posts[0].content.decode())
    assert data["report_types"] == [f"[{SENATE_EFD_PTR_TYPE_ID}]"]
    assert data["submitted_start_date"] == ["01/01/2024 00:00:00"]
    assert data["submitted_end_date"] == ["10/07/2026 23:59:59"]
    assert data_posts[0].headers["x-csrftoken"] == "fixture-token"
    assert data_posts[0].headers["referer"] == SENATE_EFD_SEARCH_URL
    assert data_posts[0].url == httpx.URL(SENATE_EFD_DATA_URL)
    fetched = {call.url.path for call in calls}
    assert PAPER_URL.removeprefix("https://efdsearch.senate.gov") not in fetched
    assert sleeps == [SENATE_EFD_PTR_PAUSE, SENATE_EFD_PTR_PAUSE]

    by_id = {row["source_record_id"]: row for row in result.records if row.get("source_record_id")}
    stock = by_id["11111111-1111-1111-1111-111111111111:1"]
    assert stock["subject"] == "Sheldon Whitehouse"
    assert stock["owner"] == "Self"
    assert stock["asset"] == "JPM"
    assert stock["asset_type"] == "common_stock"
    assert stock["eligible_equity_context"] is True
    assert stock["transaction_type"] == "Sale (Partial)"
    assert stock["transaction_date"] == "2026-09-04"
    assert stock["disclosure_date"] == "2026-10-01"
    assert stock["amount_range"] == "$15,001 - $50,000"
    assert stock["source_url"] == PTR_URL
    assert stock["provider"] == "official_senate_efd"
    assert stock["record_semantics"] == "OFFICIAL_TRANSACTION_ROW"
    assert stock["amendment"] is False

    muni = by_id["11111111-1111-1111-1111-111111111111:2"]
    assert muni["asset"] == "City of Austin TX MUNI BDS"
    assert muni["asset"] != "--"
    assert muni["asset_type"] == "municipal_bond"
    assert muni["eligible_equity_context"] is False

    etf = by_id["11111111-1111-1111-1111-111111111111:3"]
    assert etf["asset"] == "Vanguard S&P 500 ETF"
    assert etf["asset_type"] == "etf"
    assert etf["eligible_equity_context"] is False

    fund = by_id["11111111-1111-1111-1111-111111111111:4"]
    assert fund["asset"] == "Some Mutual Fund"
    assert fund["asset_type"] == "mutual_fund"
    assert fund["eligible_equity_context"] is False

    blank = by_id["11111111-1111-1111-1111-111111111111:5"]
    assert blank["asset"] == "Analog Devices Inc"
    assert blank["eligible_equity_context"] is False
    assert blank["asset_type"] is None

    amended = [row for row in result.records if row["source_url"] == AMENDMENT_URL and row.get("source_record_id")]
    assert amended
    assert all(row["amendment"] is True and row["amendment_label"] == "Amendment 1" for row in amended)
    assert {row["source_record_id"] for row in amended} == {
        "22222222-2222-2222-2222-222222222222:1",
        "22222222-2222-2222-2222-222222222222:2",
        "22222222-2222-2222-2222-222222222222:3",
        "22222222-2222-2222-2222-222222222222:4",
        "22222222-2222-2222-2222-222222222222:5",
    }

    paper = next(row for row in result.records if row["source_url"] == PAPER_URL)
    assert paper["asset"] == "FINANCIAL_DISCLOSURE_FILING"
    assert paper["transaction_type"] == "FILING"
    assert paper["record_semantics"] == "FILING_NOT_TRADE_ROW"
    assert "source_record_id" not in paper


def test_lookback_years_is_a_parameter():
    calls = []
    payload = {
        "draw": 1,
        "recordsTotal": 0,
        "recordsFiltered": 0,
        "result": "ok",
        "data": [],
    }
    result = _fetch(_handler(calls, data_body=payload), [], lookback_years=1)
    assert result.status == "HEALTHY"
    assert result.records == ()
    data = next(call for call in calls if call.url.path == "/search/report/data/")
    posted = parse_qs(data.content.decode())
    assert posted["submitted_start_date"] == ["01/01/2026 00:00:00"]
    assert posted["submitted_end_date"] == ["10/07/2026 23:59:59"]


def test_akamai_403_is_blocked_without_retry():
    calls = []
    sleeps = []
    result = _fetch(_handler(calls, data_status=403), sleeps)
    assert result.status == "BLOCKED"
    assert result.failure_kind == "BLOCKED"
    assert result.edge_reference == "18.4818d017.1791288668.5d09d74a"
    assert result.records == ()
    assert sum(1 for call in calls if call.url.path == "/search/report/data/") == 1
    assert sleeps == []
    assert not any(call.url.path.startswith("/search/view/") for call in calls)


def test_home_403_is_blocked_before_agreement():
    calls = []
    result = _fetch(_handler(calls, home_status=403), [])
    assert result.status == "BLOCKED"
    assert result.edge_reference == "18.4818d017.1791288668.5d09d74a"
    assert [call.method for call in calls] == ["GET"]


def test_429_is_rate_limit_without_retry():
    calls = []
    sleeps = []
    result = _fetch(_handler(calls, data_status=429), sleeps)
    assert result.status == "RateLimit"
    assert result.failure_kind == "RateLimit"
    assert result.records == ()
    assert sum(1 for call in calls if call.url.path == "/search/report/data/") == 1
    assert sleeps == []


def test_data_503_retries_then_returns_rows():
    calls = []
    sleeps = []
    result = _fetch(_handler(calls, fail_data_times=1), sleeps)
    assert result.status == "HEALTHY"
    assert any(row["asset"] == "JPM" for row in result.records)
    assert sleeps[0] == 1


def test_provider_default_lookback_matches_house_constant():
    provider = OfficialSenateEFDProvider(now=NOW, sleep=lambda _delay: None)
    assert provider.lookback_years == HOUSE_FILING_YEAR_LOOKBACK


def test_negative_lookback_raises_before_requests():
    calls = []
    with pytest.raises(ValueError, match="lookback_years"):
        _fetch(_handler(calls), [], lookback_years=0)
    assert calls == []
