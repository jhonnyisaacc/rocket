"""Offline acceptance tests. No credentials, requests, signatures or broadcasts."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pilot_capture import Capture as RealCapture, CAPS, cost, OUT, BASE, digest, stable
from pilot_model import State, Fees, ceildiv, buy_exact_output, buy_exact_input, sell, meets_slippage, continuous
from pilot_decode import load_evidence, strict_events, trade_instructions, validate_trade, order_transactions, OLD
from pilot_replay import build_report, simulate, covered, state_at, TOKEN_ACCOUNT_DEPOSIT


def Capture(root,transport,deadline=None):
    """Existing mock-transport tests now declare a bounded test session."""
    return RealCapture(root,transport,deadline=deadline,config={
        'deadline_at':'2099-01-01T00:00:00Z','helius_credit_cap':1000,'credit_buckets':CAPS})


class IntegerQuotes(unittest.TestCase):
    def setUp(self):
        self.state=State(30_000_000_000,1_000_000_000_000,10_000_000_000,800_000_000_000)

    def test_ordinary_buy_floor_plus_one_even_when_divisible(self):
        q=buy_exact_output(State(100,200,50,150),100,Fees(0,0,0,0))
        self.assertEqual(q['gross'],101)

    def test_exact_input_published_minus_one_not_fitted_constant(self):
        for budget in [2,101,10000,10001,100000000]:
            q=buy_exact_input(self.state,budget,Fees(0,0,0,0))
            self.assertEqual(q['tokens'],(budget-1)*self.state.tokens//(self.state.sol+budget-1))
            self.assertLessEqual(q['cash'],budget)

    def test_fee_rounding_and_budget_conservation_boundaries(self):
        for budget in range(100,15000,7):
            q=buy_exact_input(self.state,budget)
            self.assertLessEqual(q['cash'],budget)
            self.assertGreaterEqual(q['unused_budget'],0)
        self.assertEqual(ceildiv(10000,10000),1)
        self.assertEqual(ceildiv(10001,10000),2)

    def test_sell_integer_floor_and_fees(self):
        q=sell(self.state,123456789)
        self.assertEqual(q['gross'],123456789*self.state.sol//(self.state.tokens+123456789))
        self.assertEqual(q['cash'],q['gross']-q['fees']['charged'])

    def test_buyback_is_split_not_additive_trade_fee(self):
        f=Fees().amounts(1_466_666_666)
        self.assertEqual(f['protocol'],13933334)
        self.assertEqual(f['buyback'],6966667)
        self.assertEqual(f['cashback'],4400000)
        self.assertEqual(f['charged'],18333334)
        self.assertEqual(f['protocol_retained']+f['buyback'],f['protocol'])

    def test_liquidity_and_completion_fail_closed(self):
        with self.assertRaises(ValueError):sell(State(100,200,0,100),100)
        with self.assertRaises(ValueError):buy_exact_output(State(100,200,10,10),11)
        with self.assertRaises(ValueError):buy_exact_input(State(100,200,10,1),100)
        with self.assertRaises(ValueError):buy_exact_input(self.state,1)

    def test_slippage_integer_floor(self):
        self.assertTrue(meets_slippage(10000,9800))
        self.assertFalse(meets_slippage(10000,9799))


class CaptureGuards(unittest.TestCase):
    def test_cache_reuse_zero_new_requests_and_immutable(self):
        with tempfile.TemporaryDirectory() as root:
            calls=[]
            client=Capture(root,lambda request:calls.append(request) or {'result':{'signatures':[]}})
            params=[1,{'transactionDetails':'signatures'}]
            first=client.call('getBlock',params)
            path=Path(root)/(first['request_key']+'.json');before=path.read_bytes()
            second=client.call('getBlock',params)
            self.assertEqual(first,second);self.assertEqual(len(calls),1)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(len((Path(root)/'credits.jsonl').read_text().splitlines()),1)

    def test_hard_cap_before_dispatch(self):
        with tempfile.TemporaryDirectory() as root:
            calls=[]
            (Path(root)/'credits.jsonl').write_text(json.dumps(dict(request_key='prior',bucket='state',reserved_credits=1000))+'\n')
            with self.assertRaisesRegex(ValueError,'Session credit cap'):
                Capture(root,lambda r:calls.append(r)).call('getBlock',[1,{'transactionDetails':'signatures'}])
            self.assertEqual(calls,[])

    def test_bucket_cap_before_dispatch(self):
        with tempfile.TemporaryDirectory() as root:
            calls=[]
            (Path(root)/'credits.jsonl').write_text(json.dumps(dict(request_key='prior',bucket='wallets',reserved_credits=200))+'\n')
            with self.assertRaisesRegex(ValueError,'Bucket credit cap'):
                Capture(root,lambda r:calls.append(r)).call('getBlock',[1,{'transactionDetails':'signatures'}],bucket='wallets')
            self.assertEqual(calls,[])

    def test_no_automatic_retry_and_no_secret_exception(self):
        with tempfile.TemporaryDirectory() as root:
            def fail(request):raise RuntimeError('sensitive URL and secret should never be echoed')
            client=Capture(root,fail);params=[1,{'transactionDetails':'signatures'}]
            with self.assertRaises(RuntimeError) as caught:client.call('getBlock',params)
            self.assertEqual(str(caught.exception),'Capture failed: RuntimeError')
            with self.assertRaisesRegex(ValueError,'Prior dispatch unresolved'):client.call('getBlock',params)

    def test_disallow_writes_unbounded_and_expensive_modes(self):
        for method,params in [('sendTransaction',[]),('getBlock',[1,{'transactionDetails':'full'}]),
                              ('getTransactionsForAddress',['x',{'transactionDetails':'full','limit':1000}])]:
            with self.assertRaises(ValueError):cost(method,params)

    def test_corrupt_cache_no_silent_refetch(self):
        with tempfile.TemporaryDirectory() as root:
            client=Capture(root,lambda r:{'result':{'signatures':[]}})
            params=[1,{'transactionDetails':'signatures'}];saved=client.call('getBlock',params)
            saved['response']['result']['signatures']=['tampered']
            (Path(root)/(saved['request_key']+'.json')).write_text(json.dumps(saved))
            with self.assertRaisesRegex(ValueError,'Cache integrity'):client.call('getBlock',params)

    def test_expired_session_cache_only(self):
        with tempfile.TemporaryDirectory() as root:
            params=[1,{'transactionDetails':'signatures'}]
            saved=Capture(root,lambda r:{'result':{'signatures':[]}}).call('getBlock',params)
            expired=Capture(root,lambda r:self.fail('No request after deadline'),deadline='2000-01-01T00:00:00Z')
            self.assertEqual(expired.call('getBlock',params),saved)
            with self.assertRaisesRegex(ValueError,'session expired'):expired.call('getBlock',[2,params[1]])

    def test_failed_rpc_capture_retains_safe_code_only(self):
        with tempfile.TemporaryDirectory() as root:
            client=Capture(root,lambda r:{'error':{'code':-32015,'message':'not supported SECRET_KEY'}})
            with self.assertRaises(RuntimeError):client.call('getBlock',[1,{'transactionDetails':'signatures'}])
            failure=json.loads(next(Path(root).glob('*.failure.json')).read_text())
            self.assertEqual(failure['provider_error_code'],-32015)
            self.assertNotIn('SECRET_KEY',json.dumps(failure))

    def test_closed_session_blocks_new_dispatch_but_allows_cache(self):
        with tempfile.TemporaryDirectory() as root:
            params=[1,{'transactionDetails':'signatures'}]
            saved=Capture(root,lambda r:{'result':{'signatures':[]}}).call('getBlock',params)
            (Path(root)/'session_completion.json').write_text('{}')
            with patch('pilot_capture.OUT',Path(root)):
                closed=Capture(root,lambda r:self.fail('Closed session dispatched'),deadline='2099-01-01T00:00:00Z')
                self.assertEqual(closed.call('getBlock',params),saved)
                with self.assertRaisesRegex(ValueError,'session closed'):closed.call('getBlock',[2,params[1]])

    def test_same_slot_order_required_not_signature_sort(self):
        def item(sig,failed=False):return {'source':'fixture','raw':{'slot':1,'blockTime':10,'meta':{'err':'failed' if failed else None},'transaction':{'signatures':[sig]}}}
        rows=[item('a'),item('b'),item('failure',True)]
        ordered,exclusions=order_transactions(rows,{})
        self.assertEqual(len(exclusions),2);self.assertEqual(len(ordered),1)
        ordered,exclusions=order_transactions(rows,{1:['b','a','failure']})
        self.assertEqual([r['raw']['transaction']['signatures'][0] for r in ordered],['b','a','failure'])
        self.assertFalse(exclusions)
        with self.assertRaisesRegex(ValueError,'missing from block'):order_transactions(rows,{1:[]})
        with self.assertRaisesRegex(ValueError,'Duplicate signatures'):order_transactions(rows,{1:['a','b','a','failure']})


class CachedPilot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence=load_evidence()
        cls.frozen=json.loads((BASE/'session_20260921_manifest.json').read_text())
        cls.report=build_report()

    def test_historical_fills_quote_from_instruction_arguments(self):
        self.assertEqual(len(self.evidence['events']),192)
        self.assertTrue(all(e['checks']['quote_matches'] and e['checks']['fees_match'] for e in self.evidence['events']))
        self.assertEqual({e['ix_name'] for e in self.evidence['events']},{'buy','sell','buy_exact_sol_in','buy_exact_quote_in'})

    def test_historical_fee_destinations_and_deposit_separation(self):
        rows=self.evidence['events']
        self.assertTrue(all(e['checks']['protocol_destination_matches'] and e['checks']['buyback_destination_matches'] for e in rows))
        treatments=[e['checks']['cashback_treatment'] for e in rows]
        self.assertEqual(treatments.count('retained_cashback'),180)
        self.assertEqual(treatments.count('retained_cashback_plus_separate_account_deposit'),5)
        self.assertEqual(treatments.count('claim_or_close_in_same_transaction; final_delta_not_gross_fee'),7)

    def test_independent_continuity_and_missing_state(self):
        transitions=self.evidence['transitions']
        self.assertEqual(sum(t['pass_all'] for t in transitions),189)
        mint=self.frozen['fixtures']['loss'];events=[e for e in self.evidence['events'] if e['mint']==mint]
        self.assertTrue(continuous(events[0],events[1]))
        self.assertFalse(continuous(events[0],events[2]))
        evidence=copy.deepcopy(self.evidence)
        next(t for t in evidence['transitions'] if t['mint']==mint)['pass_all']=False
        # Explicit failure at entry path, rather than an earlier irrelevant event.
        t=next(t for t in evidence['transitions'] if t['mint']==mint and next(e for e in events if e['signature']==t['next'])['event_time']>=1782328096)
        t['pass_all']=False
        self.assertEqual(simulate(evidence,'loss',mint,100000000,15,self.frozen)['status'],'unavailable')

    def test_duplicate_signatures_deduplicated(self):
        self.assertEqual(self.evidence['unique_transactions'],249)
        self.assertGreater(sum(i['count'] for i in self.evidence['inventory']),249)
        self.assertEqual(len({e['signature'] for e in self.evidence['events']}),192)

    def test_failed_transactions_reverted_but_fees_retained(self):
        self.assertEqual(len(self.evidence['failed']),56)
        self.assertTrue(all(not r['state_applied'] and r['fee_lamports']>0 for r in self.evidence['failed']))

    def test_truncated_logs_and_migrations_not_silently_decoded(self):
        exclusion=self.evidence['exclusions'][0]
        self.assertEqual(exclusion['reason'],'Missing or truncated logs')
        capture=json.loads((BASE/exclusion['source']).read_text())
        raw=next(r for r in capture['response']['result']['data'] if r['transaction']['signatures'][0]==exclusion['signature'])
        with self.assertRaisesRegex(ValueError,'truncated'):strict_events(raw)
        # Native-only model; no invented migration/AMM state interpolation.
        clean=next(e for e in self.evidence['events'] if e['mint']==self.frozen['fixtures']['loss'])
        self.assertEqual(clean['quote_mint'],'11111111111111111111111111111111')
        self.assertFalse(any('amm' in e['source'] for e in self.evidence['events']))

    def test_caught_failed_cpi_not_treated_as_successful_fill(self):
        raw=copy.deepcopy(json.loads((OLD/'losing_cycle_market.json').read_text())['response']['result']['data'][0])
        raw['meta']['err']=None
        raw['meta']['logMessages']=['Program TEST invoke [1]','Program TEST failed: simulated error']
        with self.assertRaisesRegex(ValueError,'Failed invocation'):strict_events(raw)

    def test_unrecognized_migration_or_nontrade_rejected(self):
        with patch('pilot_decode.strict_events',return_value=[]):
            evidence=load_evidence()
        self.assertFalse(evidence['events'])
        self.assertTrue(all('non-single-trade' in e['reason'] for e in evidence['exclusions']))

    def test_routed_event_user_never_promoted_to_economic_trader(self):
        self.assertTrue(all(e['economic_trader'] is None for e in self.evidence['events']))
        routed=[e for e in self.evidence['events'] if e['ix_name']=='buy_exact_quote_in']
        self.assertTrue(routed)
        self.assertTrue(all('not automatically' in e['attribution'] for e in routed))

    def test_entry_exit_delays_and_fixed_horizon(self):
        for row in self.report['results']:
            self.assertEqual(row['modeled_entry_time'],row['source_event_time']+row['delay_seconds'])
            self.assertEqual(row['modeled_exit_time'],row['source_event_time']+60+2*row['delay_seconds'])
            self.assertIsNone(row['source_available_at'])

    def test_slippage_rejections_and_primary_negative_result(self):
        rows=self.report['results']
        self.assertEqual(sum(r['status']=='simulated' for r in rows),6)
        self.assertEqual(sum(r['status']=='rejected' for r in rows),12)
        primary=next(r for r in rows if r['case']=='loss' and r['size_lamports']==100000000 and r['delay_seconds']==15)
        self.assertEqual(primary['net_modeled_lamports'],-45596413)
        self.assertTrue(all(r['net_modeled_lamports'] is None for r in rows if r['status']!='simulated'))

    def test_exit_rejection_keeps_inventory_no_fake_return(self):
        with patch('pilot_replay.meets_slippage',side_effect=[True,False]):
            result=simulate(self.evidence,'loss',self.frozen['fixtures']['loss'],100000000,15,self.frozen)
        self.assertEqual(result['rejected_stage'],'exit')
        self.assertGreater(result['remaining_tokens'],0)
        self.assertIsNone(result['net_modeled_lamports'])

    def test_missing_exit_liquidity_unavailable(self):
        with patch('pilot_replay.sell',side_effect=ValueError('Insufficient exit liquidity')):
            result=simulate(self.evidence,'loss',self.frozen['fixtures']['loss'],100000000,15,self.frozen)
        self.assertEqual(result['status'],'unavailable')
        self.assertIsNone(result['net_modeled_lamports'])

    def test_missing_anchor_unavailable_not_exception(self):
        evidence=copy.deepcopy(self.evidence);evidence['events']=[]
        result=simulate(evidence,'loss',self.frozen['fixtures']['loss'],100000000,15,self.frozen)
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['reason'],'Missing verified source buy')
        self.assertIsNone(result['net_modeled_lamports'])

    def test_fee_destination_failure_blocks_simulation(self):
        evidence=copy.deepcopy(self.evidence)
        event=next(e for e in evidence['events'] if e['mint']==self.frozen['fixtures']['loss'] and e['event_time']==1782328096)
        event['checks']['buyback_destination_matches']=False
        result=simulate(evidence,'loss',self.frozen['fixtures']['loss'],100000000,15,self.frozen)
        self.assertEqual(result['status'],'unavailable')
        self.assertIsNone(result['net_modeled_lamports'])

    def test_all_unsupported_still_yields_machine_readable_rejections(self):
        evidence=copy.deepcopy(self.evidence);evidence['events']=[];evidence['transitions']=[]
        with patch('pilot_replay.load_evidence',return_value=evidence):report=build_report()
        self.assertTrue(all(r['status']=='unavailable' for r in report['results']))

    def test_discovery_partial_windows_never_become_identity_matches(self):
        from pilot_discovery import build_discovery
        report=build_discovery()
        self.assertEqual(report['unique_transactions'],200)
        self.assertEqual(report['new_admitted_wallet_mappings'],0)
        self.assertTrue(all(not r['complete'] for r in report['capture_inventory']))
        self.assertTrue(all(r['social_identity'] is None for r in report['unattributed_flows']))
        self.assertEqual(stable(report),stable(build_discovery()))

    def test_no_rent_refund_or_cashback_double_count(self):
        for r in self.report['results']:
            if r['status']!='simulated':continue
            self.assertEqual(r['wallet_cash_change_lamports']['median'],r['net_modeled_lamports']-TOKEN_ACCOUNT_DEPOSIT)
            gross=r['exit_quote']['cash']-r['entry_quote']['cash']
            self.assertEqual(r['net_modeled_lamports'],gross-r['economic_costs']['median'])

    def test_incomplete_and_stale_coverage_unavailable(self):
        intervals=[dict(start=0,end=20,complete=False)]
        self.assertFalse(covered(intervals,1,10))
        with self.assertRaisesRegex(ValueError,'Incomplete'):state_at([],10,1,intervals,[])
        self.assertFalse(covered([dict(start=0,end=10,complete=True)],1,10))

    def test_deterministic_reproduction_no_network(self):
        with patch('pilot_capture.network',side_effect=AssertionError('Network forbidden')):
            self.assertEqual(stable(build_report()),stable(build_report()))
        self.assertLessEqual(self.report['estimated_helius_credits'],1000)
        self.assertEqual(self.report['edge'],'NO_EDGE_VALIDATED')


if __name__=='__main__':unittest.main()
