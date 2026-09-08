import pytest
from typer.testing import CliRunner

from rocket.candidates import caller_references
from rocket.cli import app
from rocket.models import ReasonCode
from rocket.providers.claim_verification import verify_claims
from rocket.providers.ism import ISMIndustryRanking, ISMReport
from rocket.providers.supadata import Transcript
from rocket.store import ResearchStore
from rocket.workflows.cava import CavaWorkflow
from rocket.workflows.disclosures import DisclosureWorkflow
from rocket.workflows.ism import IsmWorkflow
from rocket.workflows.portfolio import PortfolioState, PortfolioWorkflow, PositionState
from tests.harness import assert_research_result
from tests.workflows.test_candidate_outputs import NOW, context, trade
from tests.workflows.test_cava import RSS, FixtureTranscript
from tests.workflows.test_exact_claims import data


@pytest.mark.parametrize('scenario', ['headline', 'unmapped', 'shorts_only', 'rankings_only'])
def test_ism_reports_are_visible_without_long_candidates(tmp_path, scenario):
    rankings = [] if scenario == 'headline' else [ISMIndustryRanking('wood products', 'contracting', 1)]
    report = ISMReport('manufacturing', 'August 2026', None if scenario == 'rankings_only' else 49,
                       [], rankings, 'https://publisher.test/report')
    exposures = {'wood products': [{'ticker': 'WY', 'exposure': 'wood products', 'source': 'issuer'}]} if scenario == 'shorts_only' else {}
    result = IsmWorkflow(store=ResearchStore(tmp_path), exposures=exposures,
                         context_fetcher=lambda ts: {}).run(reports={'manufacturing': report}, now=NOW,
                                                           research_companies=scenario != 'headline')
    assert_research_result(result)
    assert result.to_dict()['presentation']['market_result']
    assert not result.to_dict()['presentation']['silent']
    if scenario == 'shorts_only':
        assert result.payload['candidates'][0]['classification'] == 'SHORT_INPUT'


@pytest.mark.parametrize('outage', [False, True])
@pytest.mark.parametrize('change', ['MONITOR', 'EXIT_CANDIDATE'])
def test_partial_portfolio_keeps_valid_transition_and_precise_diagnostics(tmp_path, outage, change):
    workflow = PortfolioWorkflow(store=ResearchStore(tmp_path))
    book = PortfolioState(positions=(PositionState('CAT', thesis='thesis'), PositionState('BE', thesis='thesis')))
    workflow.run(book, {'CAT': context(), 'BE': context()}, now=NOW)
    broken = {'provider_attempts': [{'name': 'yahoo:BE', 'status': 'UNAVAILABLE'}]} if outage else {}
    observations = {'CAT': context(technical_condition='weak') if change == 'MONITOR' else context(invalidation=True), 'BE': broken}
    result = workflow.run(book, observations, now=NOW)
    assert_research_result(result)
    assert result.to_dict()['presentation']['market_result']
    assert not result.to_dict()['presentation']['silent']
    assert result.payload['transitions'] == [{'ticker': 'CAT', 'from': 'HOLD', 'to': change}]
    assert result.payload['position_diagnostics']['BE']
    assert {r.code for r in result.reasons} == {ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE if outage else ReasonCode.REQUIRED_EVIDENCE_MISSING}
    assert all(m.startswith('BE:') for r in result.reasons for m in r.missing)
    assert workflow.run(book, observations, now=NOW).to_dict()['presentation']['silent']
    # Recovering missing data must not invent an action transition from a diagnostic.
    recovered = workflow.run(book, {**observations, 'BE': context()}, now=NOW)
    assert recovered.payload['transitions'] == []


def test_thesis_gap_is_not_a_wallet_outage(tmp_path):
    result = PortfolioWorkflow(store=ResearchStore(tmp_path)).run(
        PortfolioState(positions=(PositionState('CAT'),)), {'CAT': context()}, now=NOW)
    assert result.to_dict()['presentation']['diagnostic_only']
    assert result.reasons[0].code is ReasonCode.REQUIRED_EVIDENCE_MISSING
    assert result.reasons[0].missing == ('CAT:thesis_missing',)
    assert not result.reasons[0].retryable


@pytest.mark.parametrize('which', ['portfolio', 'watch'])
@pytest.mark.parametrize('failure', ['missing', 'malformed', 'not_configured'])
def test_unknown_caller_coverage_blocks_disclosure_proposals(tmp_path, monkeypatch, which, failure):
    variables = {'portfolio': 'ROCKET_PORTFOLIO_STATE', 'watch': 'ROCKET_WATCH_STATE'}
    for name, variable in variables.items():
        path = tmp_path / (name + '.json')
        path.write_text('{"positions": [], "watches": []}')
        monkeypatch.setenv(variable, str(path))
    if failure == 'missing':
        (tmp_path / (which + '.json')).unlink()
    elif failure == 'malformed':
        (tmp_path / (which + '.json')).write_text('{broken')
    else:
        monkeypatch.delenv(variables[which])
        monkeypatch.delenv('NAVE_PORTFOLIO_STATE_FILE' if which == 'portfolio' else 'NAVE_QUANT_WATCH_STATE_FILE', raising=False)
    references, coverage = caller_references()
    result = DisclosureWorkflow(store=ResearchStore(tmp_path / 'store')).run(
        historical_records=[trade()], research_opportunities=True, now=NOW,
        context_fetcher=lambda ts: {t: context(105) for t in ts},
        portfolio_tickers=references['portfolio'], watch_tickers=references['watch'], cross_system_coverage=coverage)
    candidate = result.payload['opportunities'][0]
    assert candidate['classification'] == 'NEEDS_REVIEW'
    assert candidate['watch_proposal'] is None
    assert which in candidate['missing_reference_coverage']


def test_confirmed_empty_caller_book_allows_watch_research(tmp_path):
    result = DisclosureWorkflow(store=ResearchStore(tmp_path)).run(
        historical_records=[trade()], research_opportunities=True, now=NOW,
        context_fetcher=lambda ts: {t: context(105) for t in ts}, portfolio_tickers=(), watch_tickers=())
    assert result.payload['opportunities'][0]['classification'] == 'WATCH'
    assert result.payload['opportunities'][0]['watch_proposal']


def test_short_cli_documents_upstream_requirement():
    result = CliRunner().invoke(app, ['shorts', '--help'])
    assert result.exit_code == 0
    assert 'ISM/disclosures' in result.stdout
    assert 'built-in ticker' in result.stdout
    assert 'universe' in result.stdout


def test_contradicted_report_delivered_once_without_overlay(tmp_path):
    store = ResearchStore(tmp_path)
    store.save_state('cava_cursor', {'processed_video_ids': ['old-video']})
    provider = FixtureTranscript(Transcript('DXY is below 100.', 'en', 'fixture', NOW))
    workflow = CavaWorkflow(store=store)
    args = {'rss_xml': RSS, 'now': NOW, 'transcript_provider': provider,
            'corroborate': lambda v, c, t: verify_claims(c, t, fetcher=data)}
    result = workflow.run(**args)
    assert result.payload['delivery_cursor_advanced']
    assert not result.payload['cursor_advanced']
    assert not result.payload['overlay_validated']
    assert store.load_context('cava') is None
    assert workflow.run(**args).to_dict()['presentation']['silent']
    assert provider.calls == ['new-video']


def test_partial_acquisition_still_retries_after_useful_report(tmp_path):
    def fetch(measure):
        if measure == 'BTC_USD':
            raise RuntimeError('failed')
        return data(measure)
    store = ResearchStore(tmp_path)
    store.save_state('cava_cursor', {'processed_video_ids': ['old-video']})
    provider = FixtureTranscript(Transcript('DXY is above 100. BTC is above 50000.', 'en', 'fixture', NOW))
    workflow = CavaWorkflow(store=store)
    args = {'rss_xml': RSS, 'now': NOW, 'transcript_provider': provider,
            'corroborate': lambda v, c, t: verify_claims(c, t, fetcher=fetch)}
    result = workflow.run(**args)
    assert result.payload['report_ready']
    assert not result.payload['delivery_cursor_advanced']
    workflow.run(**args)
    assert provider.calls == ['new-video', 'new-video']
