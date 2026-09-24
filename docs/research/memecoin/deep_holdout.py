"""Holdout acquisition driver and coverage audit; frozen strategy is imported unchanged.

Initial one-page histories are preserved. Separately frozen diagnosed-tail queries
cover only the remaining interval, with two 100-record pages maximum each.
This is evidence completion, not retuning or a replacement token sample.
"""
import json
from collections import Counter
from deep_session import ROOT,save_new
from deep_capture import query
from deep_evidence import rows_for,trades
from deep_analysis import build_partition,order,relationship_flags
from deep_experiment import verify_lock,evaluate
from pilot_capture import digest,stamp

def tail_plan():
    path=ROOT/'holdout_tail_plan.json'
    if path.exists():return json.loads(path.read_text())
    verify_lock();panel=json.loads((ROOT/'holdout_cohort_v2.json').read_text());plans=[]
    for c in panel['selected']:
        s=rows_for('holdout-'+c['mint'])
        if s['complete']:continue
        start=s['last_event_time'] if s['last_event_time'] is not None else c['timestamp']
        plans.append(dict(name='DIAGNOSED:holdout-tail-'+c['mint'],mint=c['mint'],address=c['bonding_curve'],
            interval={'gte':start,'lt':c['timestamp']+900},page_cap=2,limit=100,
            diagnosis='Initial frozen one-page prefix has a remaining cursor; short page cannot prove absence',
            original_query_cap_unchanged=True,original_last_time=start))
    value=dict(frozen_at=stamp(),bucket='contingency',max_reserved_credits=20*len(plans),plans=plans,
        scope='Only unproven tails of existing fixed holdout token intervals; no new tokens, date widening or strategy changes')
    save_new(path,value);return value

def collect_tails():
    for p in tail_plan()['plans']:query(p['name'],p['address'],p['interval'],'contingency',2,100)

def combine_coverage(original,tail):
    """Prove continuous address coverage from an ascending prefix plus exhausted tail."""
    if original['address']!=tail['address']:raise ValueError('Tail address mismatch')
    if tail['interval']['gte']!=original['last_event_time'] or tail['interval']['lt']!=original['interval']['lt']:raise ValueError('Tail coverage gap')
    seen={}
    for item in original['rows']+tail['rows']:
        raw=item['raw'];sig=raw['transaction']['signatures'][0]
        if sig in seen and digest(seen[sig]['raw'])!=digest(raw):raise ValueError('Conflicting overlap')
        seen[sig]=item
    rows=sorted(seen.values(),key=lambda i:(i['raw']['slot'],i['raw']['transactionIndex']))
    return dict(complete=tail['complete'],address=original['address'],interval=original['interval'],rows=rows,
        failed=sum(r['raw']['meta']['err'] is not None for r in rows),records=len(rows),
        reason='Ascending initial prefix plus overlapping exhausted tail' if tail['complete'] else 'Tail remains capped',
        source_captures=list(dict.fromkeys(original['source_captures']+tail['source_captures'])))

def run_once():
    verify_lock()
    if (ROOT/'holdout_results.json').exists():raise ValueError('Holdout already evaluated; reproduce offline instead')
    # The frozen event decoder and trigger engine remain unchanged. Only the
    # provenance-backed coverage input is completed by overlapping tail queries.
    p=build_partition('holdout');proofs=[]
    for token in p['tokens']:
        c=token['creation'];original=rows_for('holdout-'+c['mint'])
        tail=rows_for('DIAGNOSED:holdout-tail-'+c['mint']);combined=combine_coverage(original,tail)
        # Retain the initially decoded events; add only genuinely new signatures.
        known={r['raw']['transaction']['signatures'][0] for r in original['rows']}
        for item in combined['rows']:
            raw=item['raw']
            if raw['transaction']['signatures'][0] in known:continue
            try:
                for e in trades(raw,c['mint']):
                    e.update(source_capture=item['source_capture'],retrieved_at=item['retrieved_at'],available_at=None,
                        age_seconds=e['timestamp']-c['timestamp'],creator_self=e['economic_owner'] in (c['creator'],c['user']),
                        transaction_fee_lamports=raw['meta']['fee'],legacy_execution_supported=False,
                        execution_limitation='September execution regime not validated')
                    token['events'].append(e)
            except (ValueError,KeyError) as exc:token['decode_failures'].append(dict(signature=raw['transaction']['signatures'][0],timestamp=raw['blockTime'],reason=str(exc)))
        token['events'].sort(key=order);token['coverage']={k:v for k,v in combined.items() if k!='rows'}
        proofs.append(token['coverage'])
    addresses=[r['address'] for r in json.loads((ROOT/'shortlist_final.json').read_text())['selected']]
    flags=json.loads((ROOT/'relationship_flags.json').read_text())['flags']+relationship_flags(p,addresses)
    save_new(ROOT/'holdout_coverage_proof.json',proofs);save_new(ROOT/'holdout_evidence.json',p)
    save_new(ROOT/'holdout_results.json',evaluate(p,addresses,flags))
    save_new(ROOT/'holdout_evaluation_audit.json',dict(evaluated_at=stamp(),evaluations=1,frozen_engine_verified=True,
        coverage_driver_added_after_lock=True,disclosure='Post-lock diagnostic tail coverage was added without changing shortlist, thresholds or frozen decoder/engine. Outcomes are retrospective; no additional untouched validation set remains.'))

if __name__=='__main__':
    import sys
    collect_tails() if sys.argv[1]=='capture' else run_once()
