import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pilot_capture import Capture, CAPS, OUT
from pilot_decode import instructions, unbase58, b58, PUMP, DISC, strict_events
from continuation_recovery import recover_candidate,recovered_evidence,SIGNATURE,EVENT_TAG
from continuation_capture import summarize_chain
from continuation_accounting import activity,build_wallet_ledger,transient_wsol_refund
from continuation_discovery import adjudicate_identity,build_panel,verify_display_offset
from continuation_report import before_after,credit_audit
from continuation_session import ROOT,UNIPCS

def config(root,**changes):
    value={'root':str(root),'deadline_at':'2099-01-01T00:00:00Z',
           'helius_credit_cap':1000,'credit_buckets':CAPS}
    value.update(changes);return value

class SessionControls(unittest.TestCase):
    def test_configuration_required_before_any_dispatch(self):
        with tempfile.TemporaryDirectory() as root:
            calls=[]
            with self.assertRaisesRegex(ValueError,'configuration required'):
                Capture(root,lambda r:calls.append(r)).call('getBlock',[1,{'transactionDetails':'signatures'}])
            self.assertEqual(calls,[])

    def test_closed_cross_session_cache_is_read_only_and_free(self):
        with tempfile.TemporaryDirectory() as old,tempfile.TemporaryDirectory() as new:
            args=('getBlock',[1,{'transactionDetails':'signatures'}])
            saved=Capture(old,lambda r:{'result':{'signatures':[]}},config=config(old)).call(*args)
            (Path(old)/'session_completion.json').write_text('{}')
            before={p.name:p.read_bytes() for p in Path(old).iterdir()}
            (Path(new)/'session_completion.json').write_text('{}')
            client=Capture(new,lambda r:self.fail('Dispatched'),config=config(new),cache_roots=[old])
            self.assertEqual(client.call(*args),saved)
            self.assertFalse((Path(new)/'credits.jsonl').exists())
            self.assertEqual(before,{p.name:p.read_bytes() for p in Path(old).iterdir()})
            with self.assertRaisesRegex(ValueError,'session closed'):
                client.call('getBlock',[2,{'transactionDetails':'signatures'}])

    def test_cannot_extend_deadline_or_change_root(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,'extend'):
                Capture(root,config=config(root,deadline_at='2020-01-01T00:00:00Z'),deadline='2099-01-01T00:00:00Z')
            with self.assertRaisesRegex(ValueError,'root mismatch'):
                Capture(root,config=config('/different'))

    def test_acquisition_cutoff_and_custom_cap(self):
        with tempfile.TemporaryDirectory() as root:
            cfg=config(root,acquisition_deadline_at='2000-01-01T00:00:00Z')
            with self.assertRaisesRegex(ValueError,'session expired'):
                Capture(root,lambda r:self.fail('Dispatched'),config=cfg).call('getBlock',[1,{'transactionDetails':'signatures'}])
            cfg=config(root,helius_credit_cap=1,credit_buckets={'state':1})
            client=Capture(root,lambda r:{'result':{'signatures':[]}},config=cfg)
            client.call('getBlock',[1,{'transactionDetails':'signatures'}])
            with self.assertRaisesRegex(ValueError,'Session credit cap'):
                client.call('getBlock',[2,{'transactionDetails':'signatures'}])

    def test_explicit_transport_recovery_is_once_and_keeps_reservation(self):
        from pilot_capture import digest
        with tempfile.TemporaryDirectory() as root:
            def fail(_):raise OSError('sensitive URL')
            args=('getBlock',[1,{'transactionDetails':'signatures'}])
            client=Capture(root,fail,config=config(root))
            with self.assertRaises(RuntimeError):client.call(*args)
            entry=json.loads((Path(root)/'credits.jsonl').read_text())
            client=Capture(root,fail,config=config(root),retry_authorizations={entry['request_key']:'Explicit diagnosed network restoration'})
            with self.assertRaises(RuntimeError):client.call(*args)
            with self.assertRaisesRegex(ValueError,'no automatic retry'):client.call(*args)
            ledger=[json.loads(s) for s in (Path(root)/'credits.jsonl').read_text().splitlines()]
            self.assertEqual(sum(e['reserved_credits'] for e in ledger),2)
            self.assertEqual(ledger[1]['attempt'],2)

    def test_contingency_requires_diagnosis(self):
        with tempfile.TemporaryDirectory() as root:
            client=Capture(root,lambda r:self.fail('Dispatched'),config=config(root))
            with self.assertRaisesRegex(ValueError,'diagnosed'):
                client.call('getBlock',[1,{'transactionDetails':'signatures'}],bucket='contingency')

class EmbeddedRecovery(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads((OUT/'412f7de944205ee591c839b67199c662e398f576e2a95ba7743b8445cfb15992.json').read_text())['response']['result']

    def event_ix(self,raw):
        return next(i for _,_,i in instructions(raw) if i.get('programId')==PUMP and 'data' in i and unbase58(i['data'])[:16]==EVENT_TAG+DISC)

    def test_recovery_closes_both_independent_neighbors(self):
        evidence,result=recovered_evidence()
        self.assertEqual(result['status'],'recovered')
        self.assertEqual(len(evidence['events']),193)
        self.assertEqual(sum(t['pass_all'] for t in evidence['transitions']),191)
        self.assertEqual(len(evidence['exclusions']),0)
        self.assertIsNone(result['event']['economic_trader'])
        self.assertEqual(result['new_helius_credits'],0)

    def test_default_still_rejects_truncation(self):
        with self.assertRaisesRegex(ValueError,'truncated'):strict_events(self.raw)

    def test_wrong_signature_failed_transaction_authority_and_order(self):
        for mutate in [lambda r:r['transaction']['signatures'].__setitem__(0,'other'),
                       lambda r:r['meta'].__setitem__('err',{'failed':True}),
                       lambda r:self.event_ix(r).__setitem__('accounts',['wrong']),
                       lambda r:self.event_ix(r).__setitem__('stackHeight',2)]:
            raw=copy.deepcopy(self.raw);mutate(raw)
            with self.assertRaises(ValueError):recover_candidate(raw)

    def test_short_payload_and_duplicate_event_rejected(self):
        raw=copy.deepcopy(self.raw);ix=self.event_ix(raw);ix['data']=b58(unbase58(ix['data'])[:32])
        with self.assertRaises(ValueError):recover_candidate(raw)
        raw=copy.deepcopy(self.raw)
        raw['meta']['innerInstructions'][0]['instructions'].append(copy.deepcopy(self.event_ix(raw)))
        with self.assertRaisesRegex(ValueError,'ambiguous'):recover_candidate(raw)

    def test_conflicting_log_payload_rejected(self):
        raw=copy.deepcopy(self.raw)
        raw['meta']['logMessages'].append('Program data: '+base64.b64encode(DISC+b'conflict').decode())
        with self.assertRaisesRegex(ValueError,'Conflicting'):recover_candidate(raw)

    def test_balance_disagreement_prevents_admission(self):
        from continuation_recovery import candidate_decoder
        from pilot_decode import load_evidence
        evidence=load_evidence(event_decoder=candidate_decoder)
        target=next(t for t in evidence['transitions'] if t['next']==SIGNATURE)
        target['pass_all']=False
        with patch('continuation_recovery.load_evidence',return_value=evidence):
            _,result=recovered_evidence()
        self.assertEqual(result['status'],'unavailable')

    def test_replay_keeps_rejections_but_repairs_exit_coverage(self):
        evidence,_=recovered_evidence();report=before_after(evidence)
        self.assertEqual(report['results_by_status'],{'simulated':6,'rejected':12})
        winners=[r for r in report['results'] if r['case']=='winner']
        self.assertTrue(all(r['status']=='rejected' and r['exit_coverage_supported'] for r in winners))
        self.assertTrue(all(r['net_modeled_lamports'] is None for r in winners))
        self.assertTrue(all(r['before']['net_modeled_lamports']==r['after']['net_modeled_lamports'] for r in report['comparisons']))

    def test_anchor_tag_matches_pinned_source(self):
        text=(ROOT/'sources'/'anchor_event_tag.rs').read_text()
        self.assertIn('0x1d9acb512ea545e4',text)
        self.assertEqual(EVENT_TAG,int('1d9acb512ea545e4',16).to_bytes(8,'little'))

def page(token=None,next_token=None,signature='a',time=11):
    options={'transactionDetails':'full','limit':100,'filters':{'blockTime':{'gte':10,'lt':20}}}
    if token:options['paginationToken']=token
    raw={'blockTime':time,'slot':1,'meta':{'err':None},'transaction':{'signatures':[signature]}}
    return {'request':{'params':['mint',options]},'request_key':signature+str(token),
            'retrieved_at':'2026-09-21T00:00:00Z','response':{'result':{'data':[raw],'paginationToken':next_token}}}

class Coverage(unittest.TestCase):
    def test_short_page_not_exhaustion_and_empty_termination(self):
        first=page(next_token='next')
        self.assertFalse(summarize_chain([first])['complete'])
        last=page(token='next');last['response']['result']['data']=[]
        self.assertTrue(summarize_chain([first,last])['complete'])
        self.assertFalse(summarize_chain([])['complete'])

    def test_duplicate_signature_is_deduplicated_not_counted_twice(self):
        self.assertEqual(summarize_chain([page(next_token='next'),page(token='next')])['records'],1)

    def test_conflicting_duplicate_and_repeated_cursor_rejected(self):
        with self.assertRaisesRegex(ValueError,'Conflicting duplicate'):
            summarize_chain([page(next_token='next'),page(token='next',time=12)])
        with self.assertRaisesRegex(ValueError,'Repeated'):
            summarize_chain([page(next_token='next'),page(token='next',next_token='next',signature='b')])

    def test_wrong_cursor_filters_and_out_of_window_rejected(self):
        with self.assertRaisesRegex(ValueError,'Broken'):
            summarize_chain([page(next_token='next'),page(token='wrong',signature='b')])
        other=page(token='next',signature='b');other['request']['params'][1]['filters']['status']='succeeded'
        with self.assertRaisesRegex(ValueError,'filters changed'):summarize_chain([page(next_token='next'),other])
        with self.assertRaisesRegex(ValueError,'outside'):summarize_chain([page(time=20)])

    def test_actual_cate_windows_complete_with_failed_records_retained(self):
        panel=build_panel()
        self.assertEqual(panel['unique_transactions'],1231)
        self.assertEqual(panel['failed_transactions'],389)
        self.assertTrue(all(i['complete'] for i in panel['coverage']))

class IdentityAndAccounting(unittest.TestCase):
    def test_amount_matches_need_independent_timezone_corroboration(self):
        panel=build_panel()
        self.assertTrue(all(m['amount_reconciled'] for m in panel['conditional_fill_matches']))
        self.assertEqual(adjudicate_identity(panel['conditional_fill_matches'],False)['status'],'unavailable')
        self.assertEqual(panel['admitted_new_wallet_mappings'],1)
        self.assertEqual(panel['timezone_crosscheck']['supported_offset_minutes'],[-180])

    def test_conflicting_display_times_do_not_verify_timezone(self):
        data=json.loads((ROOT/'fomo_time_evidence.json').read_text())
        data['anchors'][0]['relative_minutes']=30
        self.assertFalse(verify_display_offset(data)['frozen_offset_corroborated'])

    def test_distinct_reconciled_matches_required_after_timezone_verification(self):
        match=dict(signature='a',owner='wallet',amount_reconciled=True,owner_signed=True,
                   time_in_frozen_window=True,successful=True,logs_truncated=False,
                   unique_direct_input_match_in_frozen_window=True)
        self.assertEqual(adjudicate_identity([match,match],True)['status'],'unavailable')
        second=dict(match,signature='b',amount_reconciled=False)
        self.assertEqual(adjudicate_identity([match,second],True)['status'],'unavailable')
        second.update(amount_reconciled=True)
        self.assertTrue(adjudicate_identity([match,second],True)['status'].startswith('admitted'))
        second['owner']='different'
        self.assertEqual(adjudicate_identity([match,second],True)['status'],'unavailable')

    def test_unipcs_ledger_separates_receipts_transfer_and_buy(self):
        ledger=build_wallet_ledger()
        self.assertEqual(len(ledger['rows']),119)
        self.assertEqual(ledger['classifications']['verified_buy'],1)
        self.assertEqual(ledger['classifications']['transfer_in_not_established_buy'],111)
        self.assertEqual(ledger['classifications']['failed_attempt'],5)
        self.assertEqual(ledger['owner_paid_network_fee_lamports'],0)
        self.assertIsNone(ledger['economic_outcome'])

    def test_known_buy_fees_already_in_quote_debit_and_wsol_transient(self):
        row=next(r for r in build_wallet_ledger()['rows'] if r['classification']=='verified_buy')
        fees=sum(t['amount_raw'] for t in row['fee_like_transfers'])
        self.assertEqual(row['total_quote_debit_raw'],row['routed_quote_input_raw']+fees)
        self.assertEqual(fees,22500000)
        self.assertTrue(all(t['already_in_quote_debit'] for t in row['fee_like_transfers']))
        self.assertEqual(len(row['account_deposits']),1)
        self.assertFalse(row['account_deposits'][0]['survives_transaction'])
        self.assertEqual(row['closure_refunds_recognized_lamports'],2039280)
        self.assertEqual(row['unexplained_native_after_observed_closures_lamports'],0)
        self.assertEqual(row['observed_closure_refunds'][0]['wrapped_native_net_lamports'],0)
        self.assertEqual(row['native_delta_lamports'],0)

    def test_failed_attempt_retains_fee_but_no_reverted_transfers(self):
        raw={'slot':1,'blockTime':10,'transaction':{'signatures':['failed'],'message':{
            'accountKeys':[{'pubkey':'owner','signer':True}],'instructions':[]}},
            'meta':{'err':{'InstructionError':[0,'Error']},'fee':5000,'preBalances':[10000],
                    'postBalances':[5000],'preTokenBalances':[],'postTokenBalances':[],
                    'innerInstructions':[],'logMessages':[]}}
        row=activity(raw,'owner')
        self.assertEqual(row['owner_paid_fee_lamports'],5000)
        self.assertEqual(row['native_delta_lamports'],-5000)
        self.assertEqual(row['unexplained_native_lamports'],0)
        self.assertFalse(row['executed_token_transfers'])

    def test_truncated_or_nonzero_boundary_does_not_invent_refund(self):
        from pilot_decode import OLD,key_strings
        raw=next(r for r in json.loads((OLD/'unipcs_useless_aug30.json').read_text())['response']['result']['data'] if r['blockTime']==1788102082)
        account='DJzWGkhfsFAawMryJMdjqHenZzsmm87USmLmpyg8DHeX'
        self.assertEqual(transient_wsol_refund(raw,account,UNIPCS)['lamports'],2039280)
        changed=copy.deepcopy(raw);changed['meta']['logMessages'].append('Log truncated')
        self.assertIsNone(transient_wsol_refund(changed,account,UNIPCS))
        changed=copy.deepcopy(raw);changed['meta']['preBalances'][key_strings(changed).index(account)]=1
        self.assertIsNone(transient_wsol_refund(changed,account,UNIPCS))

    def test_competing_amount_match_blocks_identity_admission(self):
        matches=copy.deepcopy(build_panel()['conditional_fill_matches'])
        matches[0]['unique_direct_input_match_in_frozen_window']=False
        self.assertEqual(adjudicate_identity(matches,True)['status'],'unavailable')

    def test_ledger_and_panel_are_deterministic(self):
        self.assertEqual(build_wallet_ledger(),build_wallet_ledger())
        self.assertEqual(build_panel(),build_panel())

    def test_failed_reservation_not_mislabeled_success_after_manual_retry(self):
        credits=credit_audit()
        self.assertEqual(credits['reserved_credits'],180)
        self.assertEqual(credits['successful_response_credit_estimate'],160)
        self.assertEqual(credits['dispatch_reservations'],18)
        self.assertEqual(credits['successful_unique_requests'],16)

if __name__=='__main__':unittest.main()
