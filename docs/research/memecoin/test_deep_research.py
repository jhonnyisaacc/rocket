import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pilot_capture import cost,Capture
from deep_evidence import creations,trades,rows_for
from deep_session import ROOT
from deep_analysis import shortlist
from deep_experiment import triggers,ordinary,order,verify_lock
from deep_holdout import combine_coverage
from deep_audit import balance_snapshot

def event(t,owner='a',buy=True,p=100,index=None):
    return dict(timestamp=t,age_seconds=t,slot=t,transaction_index=0,outer_index=0,inner_index=0 if index is None else index,
        virtual_sol_reserves=p,virtual_token_reserves=100,economic_owner=owner,user=owner,is_buy=buy,economic_verified=True,
        creator_self=False,token_amount=100,token_owner_verified=True,signature=str((t,owner,buy,index)),mint='m')

class DeepTests(unittest.TestCase):
    def test_variable_page_pricing(self):
        for n,expected in [(1,10),(100,10),(101,20),(999,100),(1000,100)]:
            self.assertEqual(cost('getTransactionsForAddress',['a',dict(transactionDetails='full',limit=n,filters={'blockTime':{'gte':0,'lt':900}})],{'max_history_records':1000,'max_history_interval_seconds':900}),expected)
    def test_legacy_rejects_larger_pages(self):
        with self.assertRaises(ValueError):cost('getTransactionsForAddress',['a',dict(transactionDetails='full',limit=101,filters={'blockTime':{'gte':0,'lt':100}})])
    def test_extended_policy_not_other_session(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):Capture(d,config=dict(helius_credit_cap=10000,credit_buckets={'x':10000}))
    def test_unknown_config_no_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            calls=[];c=Capture(d,transport=lambda r:calls.append(r))
            with self.assertRaises(ValueError):c.call('getTransaction',['a',{}])
            self.assertFalse(calls)
    def test_large_reservation_before_dispatch(self):
        with tempfile.TemporaryDirectory() as d,patch('pilot_capture.BASE',Path(d)):
            root=Path(d)/'data/session-2026-09-21-deep-dive';calls=[]
            config=dict(session='2026-09-21-deep-dive',root=str(root),helius_credit_cap=50,credit_buckets={'cohort':50},deadline_at='2100-01-01T00:00:00Z',request_policy={'max_history_records':1000,'max_history_interval_seconds':900})
            c=Capture(root,config=config,transport=lambda r:calls.append(r))
            with self.assertRaises(ValueError):c.call('getTransactionsForAddress',['a',dict(transactionDetails='full',limit=1000,filters={'blockTime':{'gte':0,'lt':900}})],bucket='cohort')
            self.assertFalse(calls)
    def test_no_future_sell_changes_prior_trigger(self):
        es=[event(1),event(2,'b')];before=triggers({'events':es},{'a','b'})
        after=triggers({'events':es+[event(100,'a',False)]},{'a','b'})
        self.assertEqual(before,after)
    def test_only_one_first_trigger(self):
        es=[event(1),event(2),event(3)]
        self.assertEqual(triggers({'events':es},{'a'})['H1']['timestamp'],1)
    def test_h1_no_future(self):
        early=event(10,'ordinary');future=event(20,'a')
        self.assertNotIn('H1',triggers({'events':[early]}, {'a'}))
        self.assertEqual(triggers({'events':[early,future]}, {'a'})['H1'],future)
    def test_convergence_distinct(self):
        self.assertNotIn('H2',triggers({'events':[event(1),event(2)]},{'a'}))
    def test_convergence_window(self):
        self.assertNotIn('H2',triggers({'events':[event(1),event(62,'b')]},{'a','b'}))
    def test_related_pair_excluded(self):
        es=[event(1),event(2,'b')];flags=[dict(wallets=['a','b'],order=order(es[0]))]
        self.assertIn('H2',triggers({'events':es},{'a','b'},flags))
        self.assertNotIn('H2',triggers({'events':es},{'a','b'},flags,True))
    def test_future_relationship_not_used(self):
        es=[event(1),event(2,'b')];flags=[dict(wallets=['a','b'],order=order(event(20)))]
        self.assertIn('H2',triggers({'events':es},{'a','b'},flags,True))
    def test_momentum_requires_full_minute(self):
        self.assertNotIn('momentum',triggers({'events':[event(0,p=100),event(10,p=200)]},set()))
    def test_momentum_threshold(self):
        self.assertIn('momentum',triggers({'events':[event(0,p=100),event(60,p=110)]},set()))
    def test_absorption(self):
        es=[event(0,'x',p=100),event(10,'x',False,89),event(11,'a',p=90),event(12,'b',p=91)]
        self.assertIn('H3',triggers({'events':es},{'a','b'}))
    def test_absorption_negative_acquisition(self):
        es=[event(0,'x',p=100),event(10,'x',False,89),event(11,'a',p=90),event(12,'a',False,90),event(13,'a',False,90),event(14,'b',p=91)]
        self.assertNotIn('H3',triggers({'events':es},{'a','b'}))
    def test_ordinary_nearest_preceding(self):
        es=[event(1,'x'),event(2,'y'),event(3,'a'),event(4,'z')]
        self.assertEqual(ordinary(es,es[2],{'a'})['economic_owner'],'y')
    def test_ordinary_unmatched(self):
        self.assertIsNone(ordinary([event(59,'x')],event(61,'a'),{'a'}))
    def test_creator_not_trigger(self):
        e=event(1);e['creator_self']=True
        self.assertNotIn('H1',triggers({'events':[e]},{'a'}))
    def test_unsigned_not_trigger(self):
        e=event(1);e['economic_verified']=False
        self.assertNotIn('H1',triggers({'events':[e]},{'a'}))
    def test_shortlist_ignores_returns(self):
        e=event(1);e['net_return']=999
        p={'tokens':[{'first_five_buyers':[e]}]};a=shortlist(p);e['net_return']=-999
        self.assertEqual(a,shortlist(p))
    def test_cached_creation(self):
        c=json.loads((ROOT/'development_cohort_v2.json').read_text())['selected'][0]
        raw=next(r['raw'] for r in rows_for('development-'+c['mint'])['rows'] if r['raw']['transaction']['signatures'][0]==c['signature'])
        self.assertEqual(creations(raw)[0]['mint'],c['mint'])
    def test_failed_creation_never_admitted(self):
        c=json.loads((ROOT/'development_cohort_v2.json').read_text())['selected'][0]
        raw=copy.deepcopy(rows_for('development-'+c['mint'])['rows'][0]['raw']);raw['meta']['err']={'x':1}
        self.assertEqual(creations(raw),[])
    def test_truncated_trade_rejected(self):
        c=json.loads((ROOT/'development_cohort_v2.json').read_text())['selected'][0]
        raw=copy.deepcopy(rows_for('development-'+c['mint'])['rows'][0]['raw']);raw['meta']['logMessages'].append('Log truncated')
        with self.assertRaises(ValueError):trades(raw,c['mint'])
    def test_holdout_code_contamination(self):
        with patch('deep_experiment.implementation_hashes',return_value={}):
            with self.assertRaises(ValueError):verify_lock()
    def test_current_holdout_lock_intact(self):verify_lock()
    def test_missing_token_balance_not_zero(self):
        r={'transaction':{'message':{'accountKeys':['r']}},'meta':{'preBalances':[10],'preTokenBalances':[]}}
        self.assertIsNone(balance_snapshot(r,'r','m','pre')['base'])
    def test_tail_gap_rejected(self):
        a=dict(address='a',last_event_time=10,interval={'gte':0,'lt':20})
        b=dict(address='a',interval={'gte':11,'lt':20})
        with self.assertRaises(ValueError):combine_coverage(a,b)
    def test_exhausted_overlap_proves_coverage(self):
        raw={'transaction':{'signatures':['s']},'meta':{'err':None},'slot':1,'transactionIndex':0}
        a=dict(address='a',last_event_time=10,interval={'gte':0,'lt':20},rows=[{'raw':raw}],source_captures=['x'])
        b=dict(address='a',interval={'gte':10,'lt':20},rows=[{'raw':raw}],source_captures=['y'],complete=True)
        result=combine_coverage(a,b);self.assertTrue(result['complete']);self.assertEqual(result['records'],1)
        b['complete']=False;self.assertFalse(combine_coverage(a,b)['complete'])
    def test_overlap_conflicting_duplicate(self):
        raw={'transaction':{'signatures':['s']},'meta':{'err':None},'slot':1,'transactionIndex':0}
        a=dict(address='a',last_event_time=10,interval={'gte':0,'lt':20},rows=[{'raw':raw}],source_captures=['x'])
        changed=copy.deepcopy(raw);changed['slot']=2
        b=dict(address='a',interval={'gte':10,'lt':20},rows=[{'raw':changed}],source_captures=['y'],complete=True)
        with self.assertRaises(ValueError):combine_coverage(a,b)
    def test_inactive_token_retained(self):
        p=json.loads((ROOT/'development_evidence_final.json').read_text())
        t=next(t for t in p['tokens'] if t['creation']['symbol']=='BREADPITT')
        self.assertEqual(t['first_five_buyers'],[])
    def test_missing_transaction_order_rejected(self):
        c=json.loads((ROOT/'development_cohort_v2.json').read_text())['selected'][0]
        raw=copy.deepcopy(next(r['raw'] for r in rows_for('development-'+c['mint'])['rows'] if r['raw']['transaction']['signatures'][0]==c['signature']))
        raw['transactionIndex']=None
        with self.assertRaises(ValueError):creations(raw)
    def test_receipt_or_router_not_verified(self):
        c=json.loads((ROOT/'development_cohort_v2.json').read_text())['selected'][0]
        events=[e for r in rows_for('development-'+c['mint'])['rows'] for e in trades(r['raw'],c['mint'])]
        self.assertTrue(any(not e['economic_verified'] for e in events))
        self.assertTrue(all(e['quote_payment_verified'] and e['token_owner_verified'] for e in events if e['economic_verified']))

if __name__=='__main__':unittest.main()
