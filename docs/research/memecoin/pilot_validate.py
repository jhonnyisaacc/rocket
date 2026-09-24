"""Offline audit, regression runner and explicit one-session closeout.

This module has no network fallback. --close-session writes a completion marker
which prevents new dispatches by pilot_capture while allowing cached reads.
"""
import argparse
import datetime as dt
import hashlib
import json
import unittest
from unittest.mock import patch
from collections import Counter
from pilot_capture import BASE, OUT, digest, stamp
from pilot_decode import load_evidence
from pilot_replay import build_report, write_report
from pilot_discovery import build_discovery


def audit():
    ledger=[json.loads(line) for line in (OUT/'credits.jsonl').read_text().splitlines()]
    requests=[]
    for entry in ledger:
        path=OUT/(entry['request_key']+'.json')
        if path.exists():
            capture=json.loads(path.read_text())
            if digest(capture['request'])!=entry['request_key'] or digest(capture['response'])!=capture['response_sha256']:
                raise ValueError('Request/response integrity failure')
            outcome='successful_capture'
        else:
            path=OUT/(entry['request_key']+'.failure.json')
            capture=json.loads(path.read_text())
            if digest(capture['request'])!=entry['request_key']:
                raise ValueError('Failed request identity mismatch')
            outcome=capture['status']
        requests.append(dict(entry,request=capture['request'],outcome=outcome,evidence=str(path.relative_to(BASE))))
    source_manifest=json.loads((OUT/'sources'/'manifest.json').read_text())
    for source in source_manifest['sources']:
        if hashlib.sha256((OUT/'sources'/source['file']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Primary-source content hash mismatch')
    evidence=load_evidence();report=build_report();discovery=build_discovery()
    summary=dict(edge='NO_EDGE_VALIDATED',execution_gate='supported_conditionally_for_observed_native_curve_regime',
                 admitted_fills=len(evidence['events']),quote_matches=sum(e['checks']['quote_matches'] for e in evidence['events']),
                 independent_adjacent_quotes=sum(t['pass_all'] for t in evidence['transitions']),
                 adjacent_transitions=len(evidence['transitions']),
                 source_hashes_verified=len(source_manifest['sources']),request_identities_verified=len(requests),
                 results_by_status=dict(Counter(r['status'] for r in report['results'])),
                 new_wallet_mappings=discovery['new_admitted_wallet_mappings'],
                 credits_reserved=report['estimated_helius_credits'],successful_response_credit_estimate=report['successful_capture_credit_estimate'],
                 actual_provider_billing=None,requests=requests,network_calls_by_audit=0)
    (OUT/'decoded_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    write_report(report)
    (OUT/'discovery_evidence.json').write_text(json.dumps(discovery,indent=2)+'\n')
    suite=unittest.defaultTestLoader.discover(str(BASE),pattern='test_*.py')
    tests=unittest.TextTestRunner(verbosity=1).run(suite)
    summary['tests']=dict(run=tests.testsRun,failures=len(tests.failures),errors=len(tests.errors),passed=tests.wasSuccessful())
    (OUT/'validation_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if not tests.wasSuccessful():raise SystemExit('Regression failure; session not closed as complete')
    return summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--close-session',action='store_true');args=parser.parse_args()
    with patch('urllib.request.urlopen',side_effect=AssertionError('Offline audit prohibits network access')):
        summary=audit()
    print(json.dumps({k:v for k,v in summary.items() if k!='requests'},indent=2))
    if args.close_session:
        target=OUT/'session_completion.json'
        if target.exists():
            print('Existing completion marker preserved; offline revalidation passed.')
            return
        frozen=json.loads((BASE/'session_20260921_manifest.json').read_text())
        finished=stamp();elapsed=(dt.datetime.fromisoformat(finished)-dt.datetime.fromisoformat(frozen['started_at'].replace('Z','+00:00'))).total_seconds()
        completion=dict(session=frozen['session'],status='completed',started_at=frozen['started_at'],completed_at=finished,
                        elapsed_seconds=elapsed,deadline_at=frozen['deadline_at'],within_one_hour=elapsed<=3600,
                        edge='NO_EDGE_VALIDATED',execution_enabled=False,persistent_collection_enabled=False,
                        automation='PAUSED',automation_verification='Local automation TOML read during session; no mutation',
                        tests=summary['tests'],credits_reserved=summary['credits_reserved'],
                        successful_response_credit_estimate=summary['successful_response_credit_estimate'],actual_provider_billing=None,
                        completed_outputs=['2026-09-21-follower-replay-pilot.md','RESEARCH_BACKLOG.md',
                                           'session_20260921_manifest.json','session_20260921_candidates.json',
                                           'data/session-2026-09-21/decoded_evidence.json','data/session-2026-09-21/pilot_results.json',
                                           'data/session-2026-09-21/pilot_results.csv','data/session-2026-09-21/discovery_evidence.json',
                                           'data/session-2026-09-21/validation_summary.json'],
                        remaining_conditions=['Winning-case truncated log path unavailable',
                                              'Zero new social-wallet mappings; discovery histories incomplete',
                                              'No untouched sample or validated edge; no measured live execution availability'])
        with target.open('x') as stream:stream.write(json.dumps(completion,indent=2)+'\n')
        print(json.dumps(completion,indent=2))


if __name__=='__main__':main()
