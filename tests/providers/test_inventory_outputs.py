from datetime import UTC, datetime

import httpx
import pytest

from rocket.models import OperationalStatus as O
from rocket.providers.inventory import (
    MAINNET_GENESIS,
    TOKEN_PROGRAMS,
    SolanaOndoInventory,
    parse_accounts,
    rpc_order,
)

NOW = datetime(2026, 9, 8, 15, tzinfo=UTC)
ADDRESS = 'wallet'
MINT = 'mint'
REGISTRY = {MINT: {'ticker': 'BE', 'classification': 'tokenized_equity', 'approved': True, 'source': 'official issuer mapping'}}


def account(amount='300', pubkey='account', mint=MINT, program=TOKEN_PROGRAMS[0]):
    return {'pubkey': pubkey, 'account': {'owner': program, 'data': {'parsed': {'info': {
        'owner': ADDRESS, 'mint': mint, 'tokenAmount': {'amount': amount, 'decimals': 2, 'uiAmount': None}}}}}}


def test_raw_amount_aggregation_and_unknown():
    rows, errors = parse_accounts([account(), account('200', 'second'), account('100', 'other', 'unknown')],
                                  program=TOKEN_PROGRAMS[0], address=ADDRESS, registry=REGISTRY)
    assert not errors
    assert rows[MINT]['quantity'] == 5
    assert rows['unknown']['pending_review']
    assert not rows['unknown']['managed_eligible']


@pytest.mark.parametrize('bad', [{}, {'pubkey': 'a'}, account('NaN'), account('-2')])
def test_malformed_accounts_are_explicit(bad):
    rows, errors = parse_accounts([account(), bad], program=TOKEN_PROGRAMS[0], address=ADDRESS, registry=REGISTRY)
    assert errors
    assert rows[MINT]['quantity'] == 3


def test_explicit_rpc_first(monkeypatch):
    monkeypatch.setenv('SOLANA_RPC_URL', 'https://configured.test/path?key=secret')
    monkeypatch.setenv('HELIUS_API_KEY', 'secret')
    assert rpc_order()[0] == 'https://configured.test/path?key=secret'
    assert 'helius' in rpc_order()[1]


def handler_for(primary, secondary, *, fail_primary=False, movement=False):
    calls = []
    def handler(request):
        import json
        raw = json.loads(request.content)
        method, params = raw['method'], raw['params']
        calls.append((request.url.host, method))
        if fail_primary and request.url.host == 'primary.test':
            return httpx.Response(503)
        if method == 'getGenesisHash': result = MAINNET_GENESIS
        elif method == 'getBlockTime': result = int(NOW.timestamp()) - 20
        elif method == 'getTokenAccountsByOwner':
            rows = primary if request.url.host == 'primary.test' else secondary
            result = {'context': {'slot': 1000}, 'value': rows if params[1]['programId'] == TOKEN_PROGRAMS[0] else []}
        elif method == 'getAccountInfo': result = {'value': {'owner': TOKEN_PROGRAMS[0]}}
        elif method == 'getSignaturesForAddress': result = [{'signature': 'tx'}] if movement else []
        elif method == 'getTransaction': result = {
            'meta': {'err': None, 'preTokenBalances': [{'owner': ADDRESS, 'mint': MINT, 'uiTokenAmount': {'amount': '300', 'decimals': 2}}], 'postTokenBalances': []},
            'transaction': {'message': {'instructions': [{'programId': TOKEN_PROGRAMS[0], 'parsed': {'type': 'transferChecked'}}]}}}
        else: raise AssertionError(method)
        return httpx.Response(200, json={'result': result})
    return handler, calls


def fetch(primary, secondary, **kwargs):
    previous = kwargs.pop('previous', None)
    handler, calls = handler_for(primary, secondary, **kwargs)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        r = SolanaOndoInventory(http=http, urls=['https://primary.test/?key=secret', 'https://secondary.test'], registry=REGISTRY).fetch(address=ADDRESS, now=NOW, previous=previous)
    assert 'secret' not in str(r)
    return r, calls


def test_two_source_empty_confirmation():
    r, calls = fetch([], [])
    assert r.status is O.HEALTHY
    assert r.extras['empty_confirmed']
    assert ('secondary.test', 'getTokenAccountsByOwner') in calls


def test_provider_disagreement_never_accepts_false_zero():
    r, _ = fetch([], [account()])
    assert r.status is O.UNAVAILABLE
    assert r.failure_kind == 'RPCDisagreement'
    assert not r.records


def test_fallback_recovers_without_fake_empty():
    r, _ = fetch([], [account()], fail_primary=True)
    assert r.status is O.HEALTHY
    assert r.records[0]['quantity'] == 3


def test_confirmed_zero_inspects_movement_and_preserves_identity():
    old = {MINT: {'mint': MINT, 'ticker': 'BE', 'quantity': 3, 'token_program': TOKEN_PROGRAMS[0], 'token_accounts': ['account']}}
    r, calls = fetch([], [], previous=old, movement=True)
    assert r.status is O.HEALTHY
    assert r.records[0]['quantity'] == 0
    assert r.records[0]['zero_confirmed']
    assert r.records[0]['movement']['kind'] == 'TRANSFER'
    assert ('primary.test', 'getTransaction') in calls


def test_partial_parser_can_recover_on_complete_fallback():
    r, _ = fetch([{}, account()], [account()])
    assert r.status is O.HEALTHY
    assert r.extras['parser_errors']
    assert r.extras['provider_attempts'][0]['status'] == 'PARTIAL'


def test_token2022_known_dtf_and_memecoin_classification():
    registry = {'dtf': {'ticker': 'DTF', 'classification': 'reserve_dtf', 'approved': True, 'source': 'reviewed issuer'},
                'meme': {'classification': 'memecoin', 'approved': False, 'source': 'reviewed registry'}}
    rows, errors = parse_accounts([account(mint='dtf', program=TOKEN_PROGRAMS[1]), account(mint='meme', pubkey='b', program=TOKEN_PROGRAMS[1])],
                                  program=TOKEN_PROGRAMS[1], address=ADDRESS, registry=registry)
    assert not errors
    assert rows['dtf']['managed_eligible']
    assert not rows['meme']['managed_eligible']
    assert rows['meme']['classification'] == 'memecoin'


def test_two_stale_rpcs_cannot_confirm_zero():
    import json
    base, _ = handler_for([], [])
    def handler(req):
        if json.loads(req.content)['method'] == 'getBlockTime':
            return httpx.Response(200, json={'result': int(NOW.timestamp()) - 3600})
        return base(req)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        result = SolanaOndoInventory(http=http, urls=['https://primary.test', 'https://secondary.test']).fetch(address=ADDRESS, now=NOW)
    assert result.status is O.UNAVAILABLE
    assert result.failure_kind == 'StaleRPCSnapshot'


@pytest.mark.parametrize('approved', ['yes', 'true', 1, False, None])
def test_registry_approval_must_be_literal_true(tmp_path, approved):
    from rocket.providers.inventory import FileInventory
    from rocket.store import ResearchStore
    from rocket.workflows.portfolio import PortfolioState, PortfolioWorkflow, PositionState
    from tests.workflows.test_outputs import context
    registry = {MINT: {**REGISTRY[MINT], 'approved': approved}}
    rows, errors = parse_accounts([account()], program=TOKEN_PROGRAMS[0], address=ADDRESS, registry=registry)
    assert not errors
    assert rows[MINT]['pending_review']
    assert not rows[MINT]['managed_eligible']
    book = PortfolioState(wallet_address=ADDRESS, positions=(PositionState('BE', thesis='Caller thesis', quantity=9),))
    result = PortfolioWorkflow(store=ResearchStore(tmp_path), inventory=FileInventory(tuple(rows.values()))).run(
        book, {'BE': context()}, refresh_inventory=True, now=NOW)
    assert result.payload['positions'][0]['quantity'] == 9
    assert result.payload['pending_review'][0]['mint'] == MINT
