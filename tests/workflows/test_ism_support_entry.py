"""Synthetic Sep-2026 price regression; these support levels are not live quotes."""

import json
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from rocket.candidates import evaluate_long
from rocket.cli import app
from rocket.models import ResearchResult
from rocket.providers.ism import ISMIndustryRanking, ISMReport
from rocket.workflows.ism import IsmWorkflow

NOW = datetime(2026, 10, 1, 15, tzinfo=UTC)


@pytest.fixture
def contexts():
    # Actual reported prices/old averages; prior support is synthetic because
    # the incident supplied no history. Both below-band and inside-band cases
    # are exercised, plus CAT just above its support band and a true breakdown.
    inputs = {
        'NUE': (234.35, 250.99, 234.0, 'weak'),
        'GOOGL': (337.92, 342.60, 337.0, 'weak'),
        'WMT': (104.74, 107.32, 104.0, 'weak'),
        'CAT': (827.3, 809.18, 809.18, 'healthy'),
        'BROKEN': (90.0, 105.0, 100.0, 'breakdown'),
        # Quote can dip after the last healthy history close; the 3% guard
        # still tolerates this below-band discount.
        'DISCOUNT': (98.8, 105.0, 100.0, 'healthy'),
    }
    return {
        ticker: {
            'market_state': {'current_price': price, 'as_of': NOW.isoformat(),
                             'available_at': NOW.isoformat(), 'source': 'fixture quote'},
            'technical_condition': condition,
            'technical_basis': {'average_20': average, 'low_20': support,
                                'source': 'fixture closing history', 'observed_at': NOW.isoformat()},
            'fundamentals': {'eps_growth': .1, 'pe_ttm': 25,
                             'fundamentals_source': 'SEC EDGAR fixture',
                             'available_at': NOW.isoformat()},
        }
        for ticker, (price, average, support, condition) in inputs.items()
    }


def evaluate(context):
    return evaluate_long('TEST', context, thesis='expanding industry',
                         source_reference='fixture exposure', now=NOW, entry_policy='ism_support')


def workflow(contexts):
    exposures = {'machinery': [{'ticker': t, 'exposure': 'fixture exposure',
                               'source': 'https://fixture.test/issuer'} for t in contexts]}
    report = ISMReport('manufacturing', 'September 2026', 54.5,
                       [ISMIndustryRanking('machinery', 'expanding', 1)], [],
                       'https://fixture.test/ism')
    return IsmWorkflow(exposures=exposures, context_fetcher=lambda ts: contexts), report


def test_incident_prices_and_four_entry_cases(contexts):
    results = {t: evaluate(c) for t, c in contexts.items()}
    for ticker in ('NUE', 'GOOGL', 'WMT'):
        assert results[ticker]['classification'] == 'BUY_CANDIDATE'
        assert results[ticker]['entry']['zone'][0] != contexts[ticker]['technical_basis']['average_20']
    assert results['DISCOUNT']['classification'] == 'BUY_CANDIDATE'
    assert results['DISCOUNT']['distance_to_zone_pct'] < 0  # below nominal zone
    assert results['GOOGL']['distance_to_zone_pct'] == 0
    assert results['NUE']['distance_to_zone_pct'] == 0  # inside zone
    assert results['WMT']['distance_to_zone_pct'] == 0
    assert results['CAT']['classification'] == 'WATCH'
    assert results['CAT']['distance_to_zone_pct'] > 0
    assert 'wait for pullback to' in results['CAT']['reason']
    assert results['BROKEN']['classification'] == 'WATCH'
    assert results['BROKEN']['breakdown_guard_failed']
    assert 'wait for stabilization' in results['BROKEN']['reason']


@pytest.mark.parametrize('price', [96, 97, 98, 99, 100, 102])
def test_weak_never_hands_off_unexplained_reclaim_zone(contexts, price):
    c = contexts['NUE']
    c['market_state']['current_price'] = price
    c['technical_basis']['low_20'] = 100
    row = evaluate(c)
    if row['entry_zone_low'] > price:
        assert row['breakdown_guard_failed']
        assert row['classification'] == 'WATCH'
        assert 'below support' in row['reason']
    else:
        assert row['classification'] == 'BUY_CANDIDATE'


@pytest.mark.parametrize('price,condition,expected', [
    (96.99, 'healthy', 'WATCH'), (97, 'healthy', 'BUY_CANDIDATE'),
    (99, 'weak', 'BUY_CANDIDATE'), (102, 'healthy', 'BUY_CANDIDATE'),
    (102.01, 'healthy', 'WATCH'), (100, 'breakdown', 'WATCH'),
])
def test_guard_and_zone_boundaries(contexts, price, condition, expected):
    c = contexts['NUE']
    c['market_state']['current_price'] = price
    c['technical_condition'] = condition
    c['technical_basis']['low_20'] = 100
    assert evaluate(c)['classification'] == expected


@pytest.mark.parametrize('eps,pe', [(-.01, 20), (.1, 0), (.1, 40.01)])
def test_failing_fundamentals_have_no_support_entry(contexts, eps, pe):
    c = contexts['NUE']
    c['fundamentals'].update(eps_growth=eps, pe_ttm=pe)
    row = evaluate(c)
    assert row['classification'] == 'NOT_INTERESTING'
    assert row['entry'] is None


def test_watchlist_handoff_json_cli_and_roundtrip(contexts, tmp_path, monkeypatch):
    # A failed fundamentals name must not enter the passing-name handoff.
    contexts['FAIL'] = {**contexts['NUE'], 'fundamentals': {
        **contexts['NUE']['fundamentals'], 'eps_growth': -.1}}
    w, report = workflow(contexts)
    result = w.run(now=NOW, reports={'manufacturing': report}, research_companies=True)
    data = result.to_dict()
    handoff = data['watchlist_handoff']
    assert handoff == data['payload']['watchlist_handoff']
    assert {r['ticker'] for r in handoff} == {'NUE', 'GOOGL', 'WMT', 'CAT', 'BROKEN', 'DISCOUNT'}
    for row in handoff:
        assert row['entry_zone_low'] <= row['entry_zone_high']
        assert row['invalidation'] < row['entry_zone_low']
        assert row['stop_level'] == row['invalidation']
        assert row['industry'] == 'machinery'
        assert row['reason']
        assert row['data_provenance']['fundamentals_source'] == 'SEC EDGAR fixture'
        assert row['data_provenance']['reference_month'] == '2026-09'
        assert row['research_only'] and row['execution_enabled'] is False
    assert ResearchResult.from_dict(data).to_dict()['watchlist_handoff'] == handoff
    monkeypatch.setattr(IsmWorkflow, 'run', lambda *a, **kw: result)
    monkeypatch.setattr('rocket.providers.ism.fetch_ism_report', lambda kind: report)
    cli = CliRunner().invoke(app, ['ism', '--json', '--state-dir', str(tmp_path)])
    assert cli.exit_code == 0
    emitted = json.loads(cli.stdout)
    assert emitted['watchlist_handoff'] == handoff
    assert emitted['payload']['execution_enabled'] is False


def test_empty_handoff_still_top_level():
    result = IsmWorkflow().run(now=NOW, reports={})
    assert result.to_dict()['watchlist_handoff'] == []
