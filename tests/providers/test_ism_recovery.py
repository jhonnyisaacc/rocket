from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from rocket.providers.ism import expected_reference, fetch_ism_report
from rocket.workflows.ism import IsmWorkflow

NOW = datetime(2026, 9, 8, 15, tzinfo=UTC)
FIXTURES = Path(__file__).parents[1] / 'fixtures' / 'ism'
ROUNDUP = 'https://www.ismworld.org/blog/ism-pmi-reports-roundup-august-2026-manufacturing/'
RELEASE = '/news-releases/manufacturing-pmi-august-2026.html'
OFFICIAL_FIRST = {'primary': 'ism_official_roundup', 'fallbacks': ['ism_prnewswire_archive']}


@pytest.mark.parametrize('code,expected', [(200, 'InvalidProviderData'), (404, 'UnsupportedEndpoint')])
def test_official_failure_recovers_with_diagnostics(code, expected):
    def handler(req):
        if req.url.path.endswith('sitemap.xml'):
            return httpx.Response(200, text=f'<loc>{ROUNDUP}</loc>')
        if req.url.host == 'www.ismworld.org':
            return httpx.Response(code, text=(FIXTURES / 'challenge.html').read_text())
        if req.url.path.startswith('/news/institute'):
            return httpx.Response(200, text=f'<a href="{RELEASE}">release</a>')
        return httpx.Response(200, text=(FIXTURES / 'manufacturing.html').read_text())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = fetch_ism_report('manufacturing', http=client, now=NOW, config=OFFICIAL_FIRST)
    assert report.provider_failures == (f'ism.official:{expected}',)
    assert report.provider_attempts[0]['failure_kind'] == expected
    assert report.provider_attempts[1]['status'] == 'HEALTHY'
    result = IsmWorkflow(exposures={}).run(reports={'manufacturing': report}, now=NOW)
    assert result.operational.status.value == 'PARTIAL'
    assert result.payload['reports']['manufacturing']['provider_attempts'][1]['status'] == 'HEALTHY'
    assert result.to_dict()["payload"]["execution_enabled"] is False


def test_publisher_primary_skips_official():
    calls = []
    def handler(req):
        calls.append(req.url.host)
        assert req.url.host == 'www.prnewswire.com'
        body = f'<a href="{RELEASE}">release</a>' if req.url.path.startswith('/news/institute') else (FIXTURES / 'manufacturing.html').read_text()
        return httpx.Response(200, text=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = fetch_ism_report('manufacturing', http=client, now=NOW)
    assert not report.provider_failures
    assert len(report.provider_attempts) == 1
    assert len(calls) == 2


@pytest.mark.parametrize('body', [
    '<a href="/news-releases/manufacturing-pmi-july-2026.html">stale</a>',
    f'<a href="{RELEASE}">one</a><a href="{RELEASE.replace(".html", "-other.html")}">two</a>',
])
def test_ambiguous_or_stale_archive_exhausts(body):
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=body))) as client, pytest.raises(ValueError, match='exhausted'):
        fetch_ism_report('manufacturing', http=client, now=NOW)


def test_october_release_boundary():
    before = datetime(2026, 10, 1, 13, 59, tzinfo=UTC)
    after = datetime(2026, 10, 1, 14, tzinfo=UTC)
    assert expected_reference('manufacturing', before).month == 8
    assert expected_reference('manufacturing', after).month == 9
    assert expected_reference('services', after).month == 8
    assert expected_reference('services', datetime(2026, 10, 5, 14, tzinfo=UTC)).month == 9
