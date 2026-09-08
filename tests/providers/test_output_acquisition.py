from datetime import UTC, datetime

import httpx
import pytest

from rocket.models import OperationalStatus
from rocket.providers.cava_discovery import discover_videos
from rocket.providers.ism import fetch_ism_report
from rocket.workflows.cava import CAVA_CHANNEL_ID

NOW = datetime(2026, 9, 8, 12, tzinfo=UTC)


def test_rss_primary_never_calls_supadata():
    from tests.workflows.test_cava import RSS
    calls = []
    def handler(request):
        calls.append(request.url.host)
        assert request.url.host == 'www.youtube.com'
        return httpx.Response(200, text=RSS)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        r = discover_videos(http=client, api_key='fake', now=NOW)
    assert r.result.source == 'youtube.rss'
    assert calls == ['www.youtube.com']


@pytest.mark.parametrize('channel,expected', [(CAVA_CHANNEL_ID, True), ('different-channel', False)])
def test_rss_fallback_requires_exact_channel(channel, expected):
    def handler(request):
        if request.url.host == 'www.youtube.com':
            return httpx.Response(404)
        if request.url.path.endswith('channel/videos'):
            return httpx.Response(200, json={'videoIds': ['abc123']})
        return httpx.Response(200, json={'id': 'abc123', 'channel': {'id': channel}, 'title': 'Daily discussion',
                                         'uploadDate': '2026-09-07T10:00:00Z', 'isLive': False})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        r = discover_videos(http=client, api_key='fake', now=NOW)
    assert bool(r.result) is expected
    assert len(r.attempts) == 2
    if expected:
        assert r.result.source == 'supadata.metadata'


@pytest.mark.parametrize('kind,pmi', [('manufacturing', 54.6), ('services', 55.4)])
def test_ism_publisher_archive_recovers_official_failure(kind, pmi):
    link = f'/news-releases/{kind}-pmi-at-55-august-2026-ism-{kind}-pmi-report-123.html'
    def handler(request):
        if request.url.host == 'www.ismworld.org':
            return httpx.Response(200, text='<html>Access challenge</html>')
        if request.url.path.startswith('/news/institute'):
            return httpx.Response(200, text=f'<a href="{link}">report</a>')
        return httpx.Response(200, text=f'<h1>August 2026 {kind.title()}</h1>{kind.title()} PMI registered {pmi} percent. The industries reporting growth are: Machinery.')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        r = fetch_ism_report(kind, http=client, now=NOW)
    assert r.report_month == 'August 2026'
    assert r.kind == kind
    assert r.pmi == pmi
    assert r.expanding[0].industry == 'machinery'
    assert r.provider_failures


def test_ism_archive_cannot_relabel_stale_release():
    def handler(request):
        return httpx.Response(200, text='<a href="/news-releases/services-pmi-july-2026.html">old</a>')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client, pytest.raises(ValueError, match='exhausted'):
        fetch_ism_report('services', http=client, now=NOW)


def test_news_is_optional_reporting_context():
    from rocket.providers.news import acquire_news
    class FMP:
        def configured(self): return False
    r = acquire_news(fmp=FMP(), openbb_fetcher=lambda **kwargs: [])
    assert r.result.status is OperationalStatus.HEALTHY
    assert not r.reasons
    assert r.result.records == ()
