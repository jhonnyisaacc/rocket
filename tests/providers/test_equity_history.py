"""ATR history integrity and shared chart transport regression."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from rocket.clock import NY, session_day
from rocket.providers.equity_history import completed_daily_basis, equity_history, prior_atr_14
from rocket.providers.portfolio import acquire_position_evidence
from rocket.providers.shorts import _closes

NOW = datetime(2026, 10, 1, 15, tzinfo=UTC)


def timestamps():
    day = NOW.astimezone(NY).date()
    days = []
    while len(days) < 22:
        if session_day(day):
            days.append(int(datetime(day.year, day.month, day.day, 9, 30, tzinfo=NY).timestamp()))
        day -= timedelta(days=1)
    return days[::-1]


def bars():
    return {'high': [101.] * 22, 'low': [99.] * 22, 'close': [100.] * 22}


def test_true_ranges_include_gaps_and_exclude_latest_partial_bar():
    quote = bars()
    # Prior close=100, next high=111 and low=109 => TR=11, not just 2.
    quote['high'][-2], quote['low'][-2], quote['close'][-2] = 111, 109, 110
    quote['high'][-1] = quote['low'][-1] = quote['close'][-1] = None
    assert prior_atr_14(quote) == pytest.approx((13 * 2 + 11) / 14)


@pytest.mark.parametrize('bad', [None, float('nan'), float('inf'), -1, 0])
def test_missing_invalid_prior_bars_do_not_produce_atr(bad):
    quote = bars()
    quote['high'][-3] = bad
    assert prior_atr_14(quote) is None


def test_misaligned_short_and_inverted_bars_are_unavailable():
    assert prior_atr_14({'high': [101] * 16, 'low': [99] * 15, 'close': [100] * 16}) is None
    assert prior_atr_14({'high': [101] * 15, 'low': [99] * 15, 'close': [100] * 15}) is None
    quote = bars()
    quote['low'][-3] = 102
    assert prior_atr_14(quote) is None


def test_one_chart_response_adds_atr_without_changing_short_closes(monkeypatch):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={'chart': {'result': [{
            'meta': {'regularMarketTime': int(NOW.timestamp())},
            'timestamp': timestamps(),
            'indicators': {'quote': [bars()]},
        }]}})
    monkeypatch.setattr('rocket.providers.portfolio.acquire_quotes', lambda *a, **kw: {
        'CAT': {'status': 'OK', 'price': 100, 'observation_at': NOW.isoformat(),
                'available_at': NOW.isoformat(), 'source': 'fixture'}})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        row = acquire_position_evidence(['CAT'], now=NOW, http=client)['CAT']
        assert len(requests) == 1  # OHLC/ATR share the closing history request
        assert row['technical_basis']['atr_14'] == 2
        assert row['technical_basis']['latest_close'] == 100
        assert row['technical_basis']['low_20'] == 100
        assert row['technical_basis']['ism_daily_basis']['latest_close_at'] == '2026-09-30T16:00:00-04:00'
        assert row['provider_attempts'][1]['retrieved_at'] == NOW.isoformat()
        assert _closes('CAT', client) == ([100.] * 22, NOW.isoformat())
        closes, observed, atr = equity_history('CAT', client)
        assert closes == [100.] * 22 and observed == NOW.isoformat() and atr == 2


def test_chart_host_fallback_preserves_closes():
    hosts = []
    def handle(request):
        hosts.append(request.url.host)
        if request.url.host.startswith('query2'):
            return httpx.Response(503)
        return httpx.Response(200, json={'chart': {'result': [{
            'meta': {'regularMarketTime': int(NOW.timestamp())},
            'timestamp': timestamps(),
            'indicators': {'quote': [bars()]},
        }]}})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert _closes('CAT', client)[0] == [100.] * 22
    assert hosts == ['query2.finance.yahoo.com', 'query1.finance.yahoo.com']


def chart():
    return {'timestamp': timestamps(), 'indicators': {'quote': [bars()]}}


def test_partial_bar_never_affects_completed_close_support_or_atr():
    result = chart()
    quote = result['indicators']['quote'][0]
    quote['close'][-2] = 99.5  # assessed completed close below preceding support
    baseline = completed_daily_basis(result, NOW)
    assert baseline['latest_close'] == 99.5
    assert baseline['low_20'] == 100  # assessed close cannot erase support
    for value in (10, 200, None):
        for key in ('high', 'low', 'close'):
            quote[key][-1] = value
        assert completed_daily_basis(result, NOW) == baseline


def test_new_completed_close_selected_after_session_finalization():
    result = chart()
    quote = result['indicators']['quote'][0]
    quote['close'][-1] = 100.5
    later = datetime(2026, 10, 1, 20, 20, tzinfo=UTC)
    assert completed_daily_basis(result, later)['latest_close'] == 100.5
    assert completed_daily_basis(result, later)['session'] == '2026-10-01'


def test_missing_or_stale_timestamp_history_does_not_invent_close():
    result = chart()
    del result['timestamp']
    assert completed_daily_basis(result, NOW) == {}
    result = chart()
    result['timestamp'] = result['timestamp'][:-2]
    assert completed_daily_basis(result, NOW) == {}


def test_failed_history_provider_has_retrieval_time(monkeypatch):
    monkeypatch.setattr('rocket.providers.portfolio.acquire_quotes', lambda *a, **kw: {
        'CAT': {'status': 'OK', 'price': 100, 'observation_at': NOW.isoformat(),
                'available_at': NOW.isoformat(), 'source': 'fixture'}})
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        row = acquire_position_evidence(['CAT'], now=NOW, http=client)['CAT']
    assert row['provider_attempts'][1]['status'] == 'UNAVAILABLE'
    assert row['provider_attempts'][1]['retrieved_at'] == NOW.isoformat()


def test_gap_in_completed_sessions_is_not_silently_bridged():
    result = chart()
    del result['timestamp'][-3]
    for array in result['indicators']['quote'][0].values():
        del array[-3]
    assert completed_daily_basis(result, NOW) == {}
