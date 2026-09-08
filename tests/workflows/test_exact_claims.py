from datetime import UTC, datetime

import pytest

from rocket.claims import evaluate_claim, parse_claim
from rocket.models import Evidence, EvidenceKind, Provenance
from rocket.providers.claim_verification import verify_claims
from rocket.providers.supadata import Transcript
from rocket.store import ResearchStore
from rocket.workflows.cava import CavaWorkflow
from tests.harness import assert_research_result
from tests.workflows.test_cava import RSS, FixtureTranscript

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


def parsed(text):
    return parse_claim(text, claim_id='claim', claim_date=NOW.date())


@pytest.mark.parametrize('text,measure', [
    ('DXY is above 100', 'DXY'), ('CPI YoY is above 2%', 'CPI_YOY'),
    ('Core CPI YoY is above 2%', 'CORE_CPI_YOY'), ('10Y yield is above 4%', 'US10Y'),
    ('El balance de la Fed sube esta semana', 'WALCL'), ('TGA is falling this week', 'TGA'),
    ('RRP is falling this week', 'RRP'), ('BTC is above 50000', 'BTC_USD'),
    ('S&P 500 is above 6000', 'SP500'), ('Gold futures are rising this week', 'GOLD_FUTURES'),
    ('Gold is rising this week', 'GOLD_SPOT'), ('Copper is rising this week', 'COPPER_UNSPECIFIED'),
])
def test_exact_measure_identity(text, measure):
    assert parsed(text)['exact_measure'] == measure


@pytest.mark.parametrize('text,expected', [
    ('DXY is rising this week', 'VERIFIED'), ('DXY is falling this week', 'CONTRADICTED'),
    ('DXY is not rising this week', 'CONTRADICTED'), ('DXY is not falling this week', 'VERIFIED'),
    ('DXY is above 100', 'VERIFIED'), ('DXY is below 100', 'CONTRADICTED'),
    ('DXY is not above 100', 'CONTRADICTED'), ('DXY is at 101', 'VERIFIED'),
    ('DXY is rising', 'UNVERIFIED'), ('DXY could rise this week', 'UNVERIFIED'),
    ('DXY will rise next month', 'FORECAST'),
    ('DXY is rising because liquidity increased', 'UNVERIFIED'),
])
def test_direction_level_forecast_negation(text, expected):
    rows = [{'date': '2026-08-28', 'value': 99}, {'date': '2026-09-04', 'value': 101}]
    assert evaluate_claim(parsed(text), rows)['status'] == expected


def test_explicit_month_window_not_previous_day():
    claim = parsed('DXY is falling over the last month')
    rows = [{'date': '2026-08-04', 'value': 110}, {'date': '2026-09-03', 'value': 99}, {'date': '2026-09-04', 'value': 101}]
    assert evaluate_claim(claim, rows)['status'] == 'VERIFIED'
    assert claim['window_start'] == '2026-08-04'


def test_historical_assertion_not_verified_by_current_level():
    assert evaluate_claim(parsed('DXY is above 100 on 2026-08-20'), [{'date': '2026-09-04', 'value': 101}])['status'] == 'UNVERIFIED'


def test_ambiguous_indicator_is_not_substituted():
    assert parsed('Inflation is rising')['exact_measure'] is None
    assert parsed('The dollar is rising')['exact_measure'] is None


def claim(text):
    return Evidence(source='transcript', reference=text, claim=text, kind=EvidenceKind.UNKNOWN,
                    event_time=NOW, available_at=NOW, decision_time=NOW, provenance=Provenance.PROVIDER_RESULT)


def data(measure):
    return {'measure': measure, 'source': 'official-data', 'citation': 'https://source.test/series',
            'retrieved_at': NOW.isoformat(), 'records': [{'date': '2026-08-28', 'value': 99}, {'date': '2026-09-04', 'value': 101}]}


def test_wrong_proxy_cannot_verify():
    result = verify_claims([claim('DXY is above 100')], NOW, fetcher=lambda m: data('TRADE_WEIGHTED_DOLLAR'))
    assert result.checks[0]['status'] == 'UNVERIFIED'
    assert not result.evidence


def test_opposite_claims_cannot_both_pass():
    r = verify_claims([claim('DXY is rising this week'), claim('DXY is falling this week')], NOW, fetcher=data)
    assert [c['status'] for c in r.checks] == ['VERIFIED', 'CONTRADICTED']
    assert len(r.evidence) == 1


def test_partial_report_and_forecast_persistence_without_cursor(tmp_path):
    store = ResearchStore(tmp_path)
    transcript = Transcript('DXY is above 100. DXY is below 100. BTC will rise next month. Other commentary.', 'en', 'fixture', NOW)
    w = CavaWorkflow(store=store)
    r = w.run(rss_xml=RSS, transcript_provider=FixtureTranscript(transcript), now=NOW,
              corroborate=lambda v, c, t: verify_claims(c, t, fetcher=data))
    assert_research_result(r)
    assert r.payload['report_ready']
    assert r.payload['claim_counts']['VERIFIED'] == 1
    assert r.payload['claim_counts']['CONTRADICTED'] == 1
    assert not r.payload['cursor_advanced']
    assert store.load_state('cava_cursor') is None
    forecast = next(iter(store.load_state('cava_forecasts').values()))
    assert forecast['verification_state'] == 'UNRESOLVED'
    assert forecast['later_outcome'] is None


def test_late_evidence_does_not_advance_cursor(tmp_path):
    late = {**data('DXY'), 'retrieved_at': '2026-09-04T13:00:00+00:00'}
    r = CavaWorkflow(store=ResearchStore(tmp_path)).run(rss_xml=RSS,
        transcript_provider=FixtureTranscript(Transcript('DXY is above 100.', 'en', 'fixture', NOW)), now=NOW,
        corroborate=lambda v, c, t: verify_claims(c, t, fetcher=lambda m: late))
    assert_research_result(r)
    assert not r.payload['report_ready']
    assert r.payload['claims_checked'][0]['status'] == 'UNVERIFIED'
    assert not r.payload['cursor_advanced']


@pytest.mark.parametrize('text', ['CPI is above 3%', 'DXY is above 100 and below 90', 'DXY is rising this week but not inflation', 'DXY is above 1,000'])
def test_ambiguous_unit_number_or_compound_is_not_verified(text):
    rows = [{'date': '2026-08-28', 'value': 99}, {'date': '2026-09-04', 'value': 101}]
    assert evaluate_claim(parsed(text), rows)['status'] == 'UNVERIFIED'


def test_exact_liquidity_definition_required():
    assert parsed('Net liquidity WALCL - TGA - RRP is rising this week')['exact_measure'] == 'NET_LIQUIDITY'
    assert parsed('Liquidity is rising')['exact_measure'] is None


def test_fact_evidence_retains_reproduction_observations():
    result = verify_claims([claim('DXY is above 100')], NOW, fetcher=data)
    assert result.evidence[0].metadata['observations'] == data('DXY')['records']
