from datetime import UTC, datetime, timedelta

import pytest

from rocket.models import ResearchStatus
from rocket.store import ResearchStore
from rocket.workflows.macro import MacroWorkflow
from rocket.workflows.portfolio import PortfolioState, PortfolioWorkflow, PositionState
from rocket.workflows.watch import WatchWorkflow, check_watch
from tests.harness import assert_research_result

NOW = datetime(2026, 9, 8, 15, tzinfo=UTC)


def test_watch_event_preserves_caller_rationale_and_repeat(tmp_path):
    w = WatchWorkflow(store=ResearchStore(tmp_path))
    rule = {'ticker': 'BE', 'condition': 'CROSS_ABOVE', 'threshold': 100,
            'thesis': 'Caller energy demand thesis', 'source_reference': 'caller-thesis-42'}
    assert w.run([rule], prices={'BE': 99}, now=NOW).to_dict()['presentation']['silent']
    result = w.run([rule], prices={'BE': 101}, now=NOW)
    assert_research_result(result)
    event = result.payload['events'][0]
    assert event['thesis'] == rule['thesis']
    assert event['source_reference'] == rule['source_reference']
    assert event['transition'] == 'ENTERED'
    assert event['previous_price'] == 99
    assert 'buy' not in event['interpretation']
    assert w.run([rule], prices={'BE': 102}, now=NOW).to_dict()['presentation']['silent']


def test_partial_invalid_watch_diagnostic():
    result = check_watch([{}, {'ticker': 'BE', 'condition': 'ABOVE', 'threshold': 100}], {'BE': 99}, now=NOW)
    assert result.to_dict()['presentation']['diagnostic_only']


def macro_fetch(rate=3, balance=6_000_000):
    def fetch(symbol):
        value = {'EFFR': rate, 'WALCL': balance, 'WDTGAL': 500_000, 'RRPONTSYD': 10}[symbol]
        return {'records': [{'date': (NOW-timedelta(days=28)).date().isoformat(), 'value': value},
                            {'date': NOW.date().isoformat(), 'value': value}], 'retrieved_at': NOW.isoformat()}, 'fixture'
    return fetch


def test_macro_silence_keeps_latest_context_and_material_anchor(tmp_path):
    store = ResearchStore(tmp_path)
    first = MacroWorkflow(store=store, fetcher=macro_fetch()).run(now=NOW)
    assert first.to_dict()['presentation']['market_result']
    second = MacroWorkflow(store=store, fetcher=macro_fetch()).run(now=NOW)
    assert second.to_dict()['presentation']['silent']
    assert store.load_context('macro')['retrieved_at'] == NOW.isoformat()
    third = MacroWorkflow(store=store, fetcher=macro_fetch(balance=6_100_000)).run(now=NOW)
    assert third.payload['material_change']['changed']
    assert 'liquidity_material_change' in third.payload['material_change']['reasons']
    assert third.payload['factors']['WALCL']['unit'] == 'million USD'


def context(**override):
    return {'technical_condition': 'healthy', 'market_state': {'current_price': 100,
            'as_of': NOW.isoformat(), 'available_at': NOW.isoformat(), 'source': 'fixture'}, **override}


@pytest.mark.parametrize('observation,action', [({}, 'HOLD'), ({'technical_condition': 'weak'}, 'MONITOR'),
    ({'meaningful_new_information': True}, 'REVIEW_REQUIRED'), ({'technical_condition': 'breakdown'}, 'REDUCE_CANDIDATE'),
    ({'invalidation': True}, 'EXIT_CANDIDATE')])
def test_portfolio_transitions_and_stable_silence(tmp_path, observation, action):
    w = PortfolioWorkflow(store=ResearchStore(tmp_path))
    state = PortfolioState(positions=(PositionState('BE', thesis='Keep my thesis', quantity=3),))
    first = w.run(state, {'BE': context(**observation)}, now=NOW)
    assert_research_result(first)
    assert first.payload['positions'][0]['action'] == action
    second = w.run(state, {'BE': context(**observation)}, now=NOW)
    if not observation.get('meaningful_new_information'):
        assert second.to_dict()['presentation']['silent']
    assert state.positions[0].thesis == 'Keep my thesis'
    if action == 'HOLD':
        assert first.status is ResearchStatus.NO_SETUP
