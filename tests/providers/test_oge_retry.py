from datetime import UTC, datetime

import httpx
import pytest

from rocket.providers.disclosures import OGE_API_URL, OfficialOGEExecutiveDisclosureProvider
from rocket.providers.dispatch import failure_kind

PDF = "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/abc/$FILE/Donald-J-Trump-09.8.2026-278T.pdf"


def _ok(request):
    if request.url.host != "extapps2.oge.gov":
        return httpx.Response(200, text=f"<html>{OGE_API_URL}</html>")
    if request.url.params.get("length") == "1":
        posted = datetime.now(UTC).date().isoformat()
        return httpx.Response(200, json={"data": [{"docDate": posted}], "recordsFiltered": 1})
    return httpx.Response(200, json={
        "data": [{
            "docDate": datetime.now(UTC).date().isoformat(),
            "name": "Donald J. Trump",
            "type": f'<a href="{PDF}">278-T</a>',
        }],
        "recordsFiltered": 1,
    })


def test_oge_retries_503_then_returns_the_filing():
    calls = {"n": 0}
    sleeps = []

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return _ok(request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = OfficialOGEExecutiveDisclosureProvider(http=client, sleep=sleeps.append).fetch()
    assert sleeps == [1]
    assert rows[0]["transaction_type"] == "FILING_OBSERVED"
    assert rows[0]["asset"] == "PUBLIC_FINANCIAL_DISCLOSURE"
    assert rows[0]["source_url"] == PDF


def test_oge_outage_stops_after_three_attempts():
    sleeps = []

    def handler(request):
        return httpx.Response(503)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(httpx.HTTPStatusError) as caught,
    ):
        OfficialOGEExecutiveDisclosureProvider(http=client, sleep=sleeps.append).fetch()
    assert sleeps == [1, 2]
    assert failure_kind(caught.value) == "ExternalOutage"


def test_oge_client_error_is_not_retried():
    sleeps = []
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        OfficialOGEExecutiveDisclosureProvider(http=client, sleep=sleeps.append).fetch()
    assert calls["n"] == 1
    assert sleeps == []
