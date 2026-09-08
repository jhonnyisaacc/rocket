from datetime import UTC, datetime
from unittest.mock import Mock

import httpx
import pytest

from rocket.models import OperationalStatus as O
from rocket.providers.dispatch import acquire
from rocket.providers.massive import MassiveFundamentals, reported_factors
from rocket.providers.openbb_cftc import CODES, OpenBBCFTC
from rocket.providers.protocols import ProviderResult
from rocket.providers.registry import Registry

NOW = datetime(2026, 9, 8, 15, tzinfo=UTC)


def good(source='primary'):
    return ProviderResult(O.HEALTHY, ({'available_at': '2026-09-01T12:00:00+00:00'},), NOW, source=source)


@pytest.mark.parametrize('required', [True, False])
@pytest.mark.parametrize('primary_ok,fallback_ok', [(True, True), (False, True), (False, False)])
def test_dispatch_matrix(primary_ok, fallback_ok, required):
    primary = Mock(return_value=good() if primary_ok else ProviderResult(O.UNAVAILABLE, failure_kind='Entitlement'))
    fallback = Mock(return_value=good('fallback') if fallback_ok else ProviderResult(O.UNAVAILABLE, failure_kind='NotConfigured'))
    r = acquire('test', [('primary', primary), ('fallback', fallback)], required=required)
    assert fallback.call_count == int(not primary_ok)
    assert bool(r.result) == (primary_ok or fallback_ok)
    assert bool(r.reasons) == (required and not primary_ok and not fallback_ok)
    if r.result:
        assert r.result.records[0]['available_at'] == '2026-09-01T12:00:00+00:00'
        assert r.result.source == ('primary' if primary_ok else 'fallback')
    assert all(p.retrieved_at for p in r.attempts)


def test_transient_retry_bounded_and_no_exception_secrets():
    fn = Mock(side_effect=httpx.ReadTimeout('secret-in-request'))
    r = acquire('test', [('p', fn)])
    assert fn.call_count == 2
    assert len(r.attempts) == 2
    assert 'secret' not in str(r)
    assert r.reasons[0].retryable


def test_registry_order_and_missing_implementation():
    registry = Registry({'x': {'primary': 'missing', 'fallbacks': ['implemented']}})
    registry.register('x', 'implemented', good)
    result = registry.acquire('x')
    assert result.result
    assert result.attempts[0].failure_kind == 'MissingImplementation'


def annual(year, eps, **overrides):
    return {'tickers': ['CAT'], 'cik': '0000018230', 'timeframe': 'annual',
            'period_end': f'{year}-12-31', 'filing_date': f'{year+1}-02-15',
            'fiscal_year': year, 'diluted_earnings_per_share': eps, **overrides}


def test_massive_reported_comparable_periods_and_availability():
    row = reported_factors([annual(2025, 2), annual(2024, 4)], 'CAT', NOW)
    assert row['eps_growth'] == -.5
    assert row['company_fundamentals'] is True
    assert row['eps_kind'] == 'REPORTED'
    assert row['historical_available_at'] is None
    assert row['available_at'] == NOW.isoformat()
    assert row['periods'][0]['filing_date'] == '2026-02-15'
    assert row['earnings_revision_deterioration'] is None


@pytest.mark.parametrize('override', [
    {'tickers': ['DOG']}, {'tickers': ['CAT', 'CAT.B']}, {'cik': None},
    {'timeframe': 'quarterly'}, {'filing_date': '2027-01-01'},
    {'period_end': '2024-12-31'}, {'diluted_earnings_per_share': float('nan')},
    {'diluted_earnings_per_share': None}, {'fiscal_year': 2023},
])
def test_massive_rejects_identity_period_and_eps_ambiguity(override):
    with pytest.raises(ValueError):
        reported_factors([annual(2025, 2, **override), annual(2024, 4)], 'CAT', NOW)


@pytest.mark.parametrize('code,kind', [(401, 'Authentication'), (403, 'Entitlement'), (429, 'RateLimit'), (503, 'ExternalOutage')])
def test_massive_entitlement_errors_redacted(code, kind):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(code))) as client:
        r = MassiveFundamentals(api_key='TOP-SECRET', http=client).fetch('CAT', now=NOW)
    assert r.failure_kind == kind
    assert 'TOP-SECRET' not in str(r)


def cot(code, **override):
    return {'date': '2026-09-01', 'cftc_contract_market_code': code,
            'futonly_or_combined': 'FutOnly', 'open_interest_all': 100,
            'non_commercial_positions_long_all': 10,
            'non_commercial_positions_short_all': 20, **override}


def test_openbb_exact_futures_only():
    calls = []
    def fetcher(**kwargs):
        calls.append(kwargs)
        return [cot(kwargs['code'].removeprefix('CFTC_'))]
    result = OpenBBCFTC(fetcher=fetcher).fetch(now=NOW)
    assert result.status is O.HEALTHY
    assert {r['asset'] for r in result.records} == {'BTC', 'ETH'}
    assert result.source == 'OpenBB/CFTC'
    assert all(c['futures_only'] and c['report_type'] == 'legacy' for c in calls)
    assert all(r['release_date'] is None for r in result.records)


@pytest.mark.parametrize('override', [{'futonly_or_combined': 'Combined'}, {'cftc_contract_market_code': 'invalid'},
                                       {'date': '2020-01-01'}, {'date': '2027-01-01'}, {'open_interest_all': 0}])
def test_openbb_rejects_wrong_or_stale_report(override):
    result = OpenBBCFTC(fetcher=lambda **kw: [cot(CODES['BTC'], **override)]).fetch(now=NOW)
    assert result.status is O.UNAVAILABLE
