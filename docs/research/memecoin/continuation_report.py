"""Offline deterministic continuation outputs. Never rewrites closed-session data."""
import datetime as dt
import hashlib
import json
from collections import Counter
from unittest.mock import patch
from pilot_capture import BASE,OUT,digest,stamp
from pilot_replay import simulate
from continuation_session import ROOT,MANIFEST,save_new
from continuation_recovery import recovered_evidence
from continuation_accounting import build_wallet_ledger
from continuation_discovery import build_panel

def credit_audit():
    entries=[json.loads(line) for line in (ROOT/'credits.jsonl').read_text().splitlines()]
    bykey={};captures=[]
    for row in entries:
        if digest(row['request'])!=row['request_key']:raise ValueError('Ledger request identity mismatch')
        bykey.setdefault(row['request_key'],[]).append(row)
    for key,attempts in bykey.items():
        path=ROOT/(key+'.json')
        if path.exists():
            capture=json.loads(path.read_text())
            if digest(capture['request'])!=key or digest(capture['response'])!=capture['response_sha256']:
                raise ValueError('Raw capture integrity failure')
            captures.append(capture)
    cfg=json.loads(MANIFEST.read_text());buckets=Counter()
    for row in entries:buckets[row['bucket']]+=row['reserved_credits']
    if sum(buckets.values())>cfg['helius_credit_cap'] or any(v>cfg['credit_buckets'][k] for k,v in buckets.items()):
        raise ValueError('Credit cap exceeded')
    # A later success with the same key must not make a prior failed reservation
    # count as another successful response.
    return {'reserved_credits':sum(r['reserved_credits'] for r in entries),
        'successful_response_credit_estimate':sum(c['estimated_credits'] for c in captures),
        'actual_provider_billing':None,'dispatch_reservations':len(entries),
        'successful_unique_requests':len(captures),'failed_transport_reservations':sum(len(a)-1 for a in bykey.values()),
        'buckets':dict(buckets),'request_keys':sorted(bykey),
        'failed_reservations_retained':True,'new_records_in_raw_responses':sum(len(c['response']['result'].get('data',[])) for c in captures)}

def before_after(evidence):
    frozen=json.loads((BASE/'session_20260921_manifest.json').read_text())
    previous=json.loads((OUT/'pilot_results.json').read_text())
    results=[simulate(evidence,label,mint,size,delay,frozen) for label,mint in frozen['fixtures'].items()
             for size in frozen['sizes_lamports'] for delay in frozen['delays_seconds']]
    for row in results:row['decoder_version']=evidence['decoder_version']
    bykey={(r['case'],r['size_lamports'],r['delay_seconds']):r for r in previous['results']}
    comparisons=[]
    for row in results:
        old=bykey[row['case'],row['size_lamports'],row['delay_seconds']]
        fields=('status','reason','net_modeled_lamports','exit_coverage_supported')
        comparisons.append({'case':row['case'],'size_lamports':row['size_lamports'],'delay_seconds':row['delay_seconds'],
            'before':{k:old.get(k) for k in fields},'after':{k:row.get(k) for k in fields}})
    return {'edge':'NO_EDGE_VALIDATED','simulation_kind':'historical-state execution approximation',
        'sample_role':'known-outcome development fixtures only','frozen_experiment_sha256':digest(frozen),
        'original_results_sha256':hashlib.sha256((OUT/'pilot_results.json').read_bytes()).hexdigest(),
        'results':results,'comparisons':comparisons,'results_by_status':dict(Counter(r['status'] for r in results)),
        'rules_unchanged':True,'all_original_assumptions':previous['assumptions']}

def audit_baseline():
    baseline=json.loads((ROOT/'baseline_hashes.json').read_text());changed=[];verified=[]
    for name,expected in baseline.items():
        actual=hashlib.sha256((BASE/name).read_bytes()).hexdigest()
        if actual!=expected:changed.append(name)
        else:verified.append(name)
    protected=[name for name in changed if name.startswith('data/') or name.startswith('session_20260921')]
    if protected:raise ValueError('Protected baseline artifacts changed: '+','.join(protected))
    return {'verified_unchanged_files':len(verified),'changed_implementation_or_backlog':changed,
            'all_preexisting_captures_and_closed_session_outputs_preserved':True}

def build_outputs():
    evidence,recovery=recovered_evidence();replay=before_after(evidence)
    wallet=build_wallet_ledger();panel=build_panel();credits=credit_audit()
    sources=json.loads((ROOT/'sources'/'manifest.json').read_text())
    for source in sources['sources']:
        if 'sha256' in source and hashlib.sha256((ROOT/'sources'/source['file']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Source hash mismatch')
    summary={'edge':'NO_EDGE_VALIDATED','execution_enabled':False,'automation':'PAUSED',
        'recovery_status':recovery['status'],'validated_fills':len(evidence['events']),
        'independent_adjacent_checks_passed':sum(t['pass_all'] for t in evidence['transitions']),
        'independent_adjacent_checks_total':len(evidence['transitions']),
        'replay_status_counts':replay['results_by_status'],
        'cate_unique_transactions':panel['unique_transactions'],'cate_failed_transactions':panel['failed_transactions'],
        'cate_complete_windows':sum(i['complete'] for i in panel['coverage']),
        'conditional_public_fill_amount_matches':sum(m['amount_reconciled'] for m in panel['conditional_fill_matches']),
        'new_admitted_wallet_mappings':panel['admitted_new_wallet_mappings'],
        'identity_admission':panel['identity_admission'],'unipcs_records':len(wallet['rows']),
        'unipcs_classifications':wallet['classifications'],'credits':credits,'baseline_preservation':audit_baseline(),
        'next_experiment_sha256':hashlib.sha256((ROOT/'next_experiment.json').read_bytes()).hexdigest(),
        'implementation_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(BASE.glob('*.py'))},
        'offline_network_calls':0,'actual_provider_billing':None}
    return {'recovery_result.json':recovery,'decoded_evidence.json':evidence,'pilot_results.json':replay,
            'unipcs_activity_ledger.json':wallet,'cate_identity_adjudication.json':panel,'summary.json':summary}

def main():
    import argparse,unittest
    parser=argparse.ArgumentParser();parser.add_argument('--close-session',action='store_true');parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    with patch('urllib.request.urlopen',side_effect=AssertionError('Offline reproduction prohibits network')):
        outputs=build_outputs()
        if args.verify_only:
            for name,value in outputs.items():
                if json.loads((ROOT/name).read_text())!=value:raise ValueError('Reproduction mismatch: '+name)
        else:
            for name,value in outputs.items():
                (ROOT/name).write_text(json.dumps(value,indent=2)+'\n')
        suite=unittest.defaultTestLoader.discover(str(BASE),pattern='test_*.py')
        result=unittest.TextTestRunner(verbosity=1).run(suite)
        tests={'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful()}
        if not result.wasSuccessful():raise SystemExit('Tests failed; no completion marker')
    if not args.verify_only:(ROOT/'test_results.json').write_text(json.dumps(tests,indent=2)+'\n')
    summary=outputs['summary.json'];print(json.dumps({k:v for k,v in summary.items() if k not in ('implementation_sha256','baseline_preservation')},indent=2))
    if args.close_session:
        manifest=json.loads(MANIFEST.read_text());finished=stamp()
        elapsed=(dt.datetime.fromisoformat(finished)-dt.datetime.fromisoformat(manifest['started_at'].replace('Z','+00:00'))).total_seconds()
        save_new(ROOT/'session_completion.json',{'session':manifest['session'],'status':'completed',
            'completed_at':finished,'elapsed_seconds':elapsed,'within_one_hour':elapsed<=3600,
            'edge':'NO_EDGE_VALIDATED','automation':'PAUSED','execution_enabled':False,
            'tests':tests,'credits':summary['credits'],'outputs':list(outputs),
            'limitations':['Social-wallet identity corroborated by two fills and minute-scale UI time crosscheck, not public key declaration or legal identity.',
                           'No new holdout outcomes collected or trading edge established.']})

if __name__=='__main__':main()
