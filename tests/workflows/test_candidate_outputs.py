from datetime import UTC, datetime, timedelta

import pytest

from rocket.candidates import bearish_inputs, evaluate_long, persist_candidates
from rocket.models import ResearchStatus
from rocket.providers.ism import ISMIndustryRanking, ISMReport
from rocket.store import ResearchStore
from rocket.workflows.disclosures import DisclosureWorkflow
from rocket.workflows.ism import IsmWorkflow
from rocket.workflows.shorts import ShortsWorkflow, score_candidate
from tests.harness import assert_research_result

NOW = datetime(2026, 9, 4, 15, tzinfo=UTC)


def context(price=101, **kwargs):
    return {'market_state': {'current_price': price, 'as_of': NOW.isoformat(), 'available_at': NOW.isoformat(), 'source': 'quote'},
            'technical_condition': 'healthy', 'technical_basis': {'average_20': 100, 'low_20': 90},
            'fundamentals': {'eps_growth': .1, 'pe_ttm': 20, 'available_at': NOW.isoformat(), 'fundamentals_source': 'reported-provider'}, **kwargs}


@pytest.mark.parametrize('price,expected', [(101, 'BUY_CANDIDATE'), (105, 'WATCH'), (89, 'NOT_INTERESTING')])
def test_independent_long_entry(price, expected):
    r = evaluate_long('CAT', context(price), thesis='Stored reason', source_reference='issuer', now=NOW)
    assert r['classification'] == expected
    if expected == 'WATCH':
        assert r['watch_proposal']['requires_caller_approval']
        assert r['watch_proposal']['thesis'] == 'Stored reason'


@pytest.mark.parametrize('value', [None, float('nan'), float('inf'), True, '0.1'])
def test_bad_fundamentals_cannot_buy(value):
    c = context()
    c['fundamentals']['eps_growth'] = value
    assert evaluate_long('CAT', c, thesis='reason', source_reference='issuer', now=NOW)['classification'] == 'NEEDS_REVIEW'


@pytest.mark.parametrize('field,value', [('available_at', (NOW + timedelta(seconds=1)).isoformat()), ('as_of', '2025-01-01'), ('source', None)])
def test_bad_market_cannot_buy(field, value):
    c = context()
    c['market_state'][field] = value
    assert evaluate_long('CAT', c, thesis='reason', source_reference='issuer', now=NOW)['classification'] == 'NEEDS_REVIEW'


def test_ism_company_pipeline_and_short_handoff(tmp_path):
    store = ResearchStore(tmp_path)
    reports = {'manufacturing': ISMReport('manufacturing', 'August 2026', 52,
               [ISMIndustryRanking('machinery', 'expanding', 1)], [ISMIndustryRanking('wood products', 'contracting', 1)], 'https://official.test/report')}
    exposures = {'machinery': [{'ticker': 'CAT', 'exposure': 'Equipment manufacturing', 'source': 'https://issuer.test/cat'}],
                 'wood products': [{'ticker': 'WY', 'exposure': 'Wood products', 'source': 'https://issuer.test/wy'}]}
    w = IsmWorkflow(store=store, exposures=exposures, context_fetcher=lambda tickers: {t: context() for t in tickers})
    r = w.run(reports=reports, now=NOW, research_companies=True)
    assert_research_result(r)
    assert {c['classification'] for c in r.payload['candidates']} == {'BUY_CANDIDATE', 'SHORT_INPUT'}
    assert bearish_inputs(store, NOW)[0]['ticker'] == 'WY'
    assert store.load_state('watch_state') is None


def test_conflicting_and_expired_origins_cannot_seed_shorts(tmp_path):
    store = ResearchStore(tmp_path)
    persist_candidates(store, 'ism', [{'ticker': 'CAT', 'direction': 'long'}, {'ticker': 'CAT', 'direction': 'short'}], now=NOW)
    assert not bearish_inputs(store, NOW)
    persist_candidates(store, 'ism', [{'ticker': 'CAT', 'direction': 'short'}], now=NOW)
    assert not bearish_inputs(store, NOW + timedelta(days=36))


def trade(subject='Nancy Pelosi', **kwargs):
    return {'subject': subject, 'asset': 'CAT', 'transaction_type': 'Purchase', 'transaction_date': '2026-08-04',
            'disclosure_date': '2026-08-14', 'source_url': 'https://official.test/ptr.pdf', **kwargs}


def test_person_filter_historical_overlap_and_stable_silence(tmp_path):
    store = ResearchStore(tmp_path)
    persist_candidates(store, 'ism', [{'ticker': 'CAT', 'direction': 'long'}], now=NOW)
    w = DisclosureWorkflow(store=store)
    args = {'historical_records': [trade(), trade('Donald Trump Jr.')], 'subjects': ['Nancy Pelosi'], 'research_opportunities': True,
            'context_fetcher': lambda tickers: {t: context() for t in tickers}, 'now': NOW,
            'portfolio_tickers': ['CAT'], 'watch_tickers': ['CAT']}
    r = w.run(**args)
    assert_research_result(r)
    assert len(r.payload['opportunities']) == 1
    c = r.payload['opportunities'][0]
    assert c['classification'] == 'BUY_CANDIDATE'
    assert c['overlap'] == ['ism', 'portfolio', 'watch']
    assert c['disclosure_lag_days'] == 10
    assert w.run(**args).to_dict()['presentation']['silent']


def test_historical_extended_opportunity_too_late(tmp_path):
    history = {'source': 'quotes', 'citation': 'https://quote.test/history', 'retrieved_at': NOW.isoformat(),
               'records': [{'date': '2026-08-04', 'close': 80, 'adjusted_close': 80}, {'date': NOW.date().isoformat(), 'close': 120, 'adjusted_close': 120}]}
    r = DisclosureWorkflow(store=ResearchStore(tmp_path)).run(historical_records=[trade()], research_opportunities=True,
        context_fetcher=lambda tickers: {'CAT': context(120)}, historical_price_fetcher=lambda t: history, now=NOW, portfolio_tickers=(), watch_tickers=())
    c = r.payload['opportunities'][0]
    assert c['classification'] == 'TOO_LATE'
    assert c['move_since_transaction'] == .5
    assert c['watch_proposal'] is None


def test_trump_executive_and_unknown_instrument_stays_review(tmp_path):
    r = DisclosureWorkflow(store=ResearchStore(tmp_path)).run(subjects=['Donald Trump'],
        historical_records=[trade('Donald J. Trump', asset='Issuer Bond', source_family='executive', eligible_equity_context=False)],
        research_opportunities=True, context_fetcher=lambda tickers: {}, now=NOW)
    c = r.payload['opportunities'][0]
    assert c['classification'] == 'NEEDS_REVIEW'
    assert c['ticker'] is None
    assert c['original_transaction']['source_family'] == 'executive'


def test_all_failed_disclosures_do_not_advance_history(tmp_path):
    store = ResearchStore(tmp_path)
    r = DisclosureWorkflow(store=store).run(historical_records=[trade()], research_opportunities=True,
            provider_status={'congress': {'status': 'UNAVAILABLE'}}, now=NOW)
    assert r.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert store.load_state('disclosure_history') is None
    assert store.load_state('research_candidates') is None


@pytest.mark.parametrize('origin', ['ism', 'disclosures'])
def test_shorts_consumes_canonical_origin(tmp_path, origin):
    store = ResearchStore(tmp_path)
    persist_candidates(store, origin, [{'ticker': 'CAT', 'direction': 'short', 'thesis': 'Independent bearish origin', 'sector_etf': 'XLI'}], now=NOW)
    def fetch(**kwargs):
        assert kwargs['universe'] == {'CAT': 'XLI'}
        return [{'ticker': 'CAT', 'source': 'fixture', 'event_time': NOW.isoformat(), 'available_at': NOW.isoformat(),
                 'acquisition_mode': 'LIVE', 'provider_health': 'HEALTHY', 'company_fundamentals': True,
                 'technical_breakdown': True, 'sector_weakness': True, 'valuation_support': False}]
    r = ShortsWorkflow(store=store).scan_live(snapshot_fetcher=fetch, now=NOW)
    assert_research_result(r)
    assert r.status is ResearchStatus.SETUP_FOUND
    assert r.payload['final_candidates'][0]['candidate_id'] == 'listed:CAT'
    assert r.payload['final_candidates'][0]['sources'][0]['thesis'] == 'Independent bearish origin'


def test_successful_empty_canonical_scan_is_small_message(tmp_path):
    store = ResearchStore(tmp_path)
    persist_candidates(store, 'ism', [], now=NOW)
    r = ShortsWorkflow(store=store).scan_live(now=NOW)
    assert r.status is ResearchStatus.NO_SETUP
    assert r.payload['summary'] == 'Shorts scan: no valid setup found today.'
    assert r.to_dict()['presentation'] == {'silent': False, 'market_result': False, 'diagnostic_only': False}


@pytest.mark.parametrize('value', ['UNKNOWN', 'unavailable', float('nan'), 2])
def test_unrecognized_short_factor_cannot_select(value):
    r = score_candidate({'ticker': 'CAT', 'company_fundamentals': value, 'technical_breakdown': True, 'sector_weakness': True, 'macro_regime': 'bearish'})
    assert not r['selected']
    assert r['factor_states']['company_fundamentals'] == 'UNKNOWN'


def test_failed_ism_cannot_create_successful_empty_short_universe(tmp_path):
    store = ResearchStore(tmp_path)
    r = IsmWorkflow(store=store, context_fetcher=lambda tickers: {}).run(reports={}, research_companies=True, now=NOW)
    assert r.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert store.load_state('research_candidates') is None
    assert ShortsWorkflow(store=store).scan_live(now=NOW).status is ResearchStatus.INSUFFICIENT_EVIDENCE
