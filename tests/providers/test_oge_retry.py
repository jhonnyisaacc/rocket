from datetime import UTC, datetime

import httpx
import pytest

from rocket.providers.disclosures import (
    OfficialOGEExecutiveDisclosureProvider,
    OGEProviderError,
    executive_failure_status,
)
from rocket.providers.dispatch import failure_kind

PDF = "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/abc/$FILE/Donald-J-Trump-09.8.2026-278T.pdf"
V2 = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v2/rest"
V3 = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v3/rest"


def _records(request):
    if request.url.params.get("length") == "1":
        posted = datetime.now(UTC).date().isoformat()
        return httpx.Response(200, json={"data": [{"docDate": posted}], "recordsFiltered": 1})
    return httpx.Response(
        200,
        json={
            "data": [
                {
                    "docDate": datetime.now(UTC).date().isoformat(),
                    "name": "Donald J. Trump",
                    "type": f'<a href="{PDF}">278-T</a>',
                }
            ],
            "recordsFiltered": 1,
        },
    )


def _handler(index_html):
    def handler(request):
        if request.url.host != "extapps2.oge.gov":
            return httpx.Response(200, text=index_html)
        return _records(request)

    return handler


def _ok(request):
    return _handler(f"<html>{V3}</html>")(request)


def _fetch(handler, **kwargs):
    sleeps = kwargs.pop("sleeps", None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return OfficialOGEExecutiveDisclosureProvider(
            http=client,
            sleep=sleeps.append if sleeps is not None else (lambda _delay: None),
            **kwargs,
        ).fetch()


def test_oge_retries_503_then_returns_the_filing():
    calls = {"n": 0}
    sleeps = []

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return _ok(request)

    rows = _fetch(handler, sleeps=sleeps)
    assert sleeps == [1]
    assert rows[0]["transaction_type"] == "FILING_OBSERVED"
    assert rows[0]["asset"] == "PUBLIC_FINANCIAL_DISCLOSURE"
    assert rows[0]["source_url"] == PDF


def test_oge_outage_stops_after_three_attempts():
    sleeps = []

    def handler(request):
        return httpx.Response(503)

    with pytest.raises(httpx.HTTPStatusError) as caught:
        _fetch(handler, sleeps=sleeps)
    assert sleeps == [1, 2]
    assert failure_kind(caught.value) == "ExternalOutage"
    assert executive_failure_status(caught.value)["reason"] == "http_503"


def test_oge_client_error_is_not_retried():
    sleeps = []
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404)

    with pytest.raises(httpx.HTTPStatusError):
        _fetch(handler, sleeps=sleeps)
    assert calls["n"] == 1
    assert sleeps == []


def test_oge_index_v3_only_requests_v3():
    requested = []

    def handler(request):
        requested.append(str(request.url.copy_with(query=None)))
        return _handler(f"<html>&quot;{V3}&quot;</html>")(request)

    rows = _fetch(handler)
    assert rows[0]["source_url"] == PDF
    assert any(url.endswith("/API.xsp/v3/rest") for url in requested)
    assert not any("/API.xsp/v2/rest" in url for url in requested)


def test_oge_index_with_v2_and_v3_uses_v3():
    requested = []

    def handler(request):
        requested.append(str(request.url.copy_with(query=None)))
        return _handler(f"<html>{V2} {V3}</html>")(request)

    _fetch(handler)
    assert any(url.endswith("/API.xsp/v3/rest") for url in requested)
    assert not any(url.endswith("/API.xsp/v2/rest") for url in requested)


def test_oge_index_without_api_marker_is_invalid_provider_data():
    sleeps = []
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, text="<html>no records api</html>")

    with pytest.raises(OGEProviderError) as caught:
        _fetch(handler, sleeps=sleeps)
    assert caught.value.reason == "oge_index_api_marker_missing"
    assert failure_kind(caught.value) == "InvalidProviderData"
    assert failure_kind(caught.value) != "ExternalOutage"
    assert calls["n"] == 1
    assert sleeps == []
    status = executive_failure_status(caught.value)
    assert status["reason"] == "oge_index_api_marker_missing"
    assert status["failure_kind"] == "InvalidProviderData"


def test_executive_failure_status_drops_urls_and_free_text():
    class Leaky(Exception):
        def __init__(self) -> None:
            self.reason = "https://user:secret@example.test/API.xsp/v3/rest"
            super().__init__(self.reason)

    leaked = executive_failure_status(Leaky())
    assert "reason" not in leaked
    assert "secret" not in str(leaked)
    plain = executive_failure_status(
        ValueError("OGE collection schema missing its public records API")
    )
    assert "reason" not in plain
    assert plain["failure_kind"] == "InvalidProviderData"

    request = httpx.Request("GET", "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v3/rest")
    response = httpx.Response(503, request=request)
    transport = httpx.ConnectError("timed out calling https://user:secret@example.test")
    http_status = executive_failure_status(
        httpx.HTTPStatusError("boom", request=request, response=response)
    )
    assert http_status["reason"] == "http_503"
    assert "extapps2" not in http_status["reason"]
    moved = executive_failure_status(transport)
    assert moved == {
        "status": "UNAVAILABLE",
        "failure_kind": "ExternalOutage",
        "reason": "transport_error",
    }
