"""Offline reproducibility and consolidated audit for the bounded deep dive."""
import hashlib
import json
from collections import Counter
from deep_session import ROOT,SEEDS,save_new
from deep_audit import credit_audit,verify_offline,independent_continuity,wallet_behavior
from deep_analysis import build_partition,shortlist,relationship_flags
from deep_experiment import evaluate,verify_lock
from deep_evidence import rows_for,trades
from continuation_accounting import activity,transfers,USDC
from pilot_capture import digest,stamp

def public_amount_check():
    values={295628,139170,334066,100582,207208,321211};matches=[]
    for item in rows_for('public-NBA-trey-INURANUS')['rows']:
        raw=item['raw'];net=Counter()
        for t in transfers(raw):
            if t['mint']==USDC:
                net[t.get('destination_owner')]+=t['amount_raw'];net[t.get('source_owner')]-=t['amount_raw']
        for owner,value in net.items():
            if (value+5000)//10000 in values:matches.append(dict(owner=owner,raw_usdc=value,signature=raw['transaction']['signatures'][0]))
    return dict(matches=matches,coverage_complete=False,identity_admitted=False,
        method='Rounded positive owner USDC net credits versus the six displayed sell amounts; unknown USD valuation basis prevents identity admission regardless of amount-only match.')

def reproduce():
    verify_lock();cache=verify_offline()
    dev=build_partition('development');frozen_dev=json.loads((ROOT/'development_evidence_final.json').read_text())
    if digest(dev)!=digest(frozen_dev):raise AssertionError('Development evidence changed')
    s=shortlist(dev);saved_s=json.loads((ROOT/'shortlist_final.json').read_text())
    if s!=saved_s:raise AssertionError('Shortlist changed')
    addresses=[w['address'] for w in s['selected']]
    flags=relationship_flags(dev,addresses)
    if evaluate(dev,addresses,flags)!=json.loads((ROOT/'development_results.json').read_text()):raise AssertionError('Development results changed')
    held=json.loads((ROOT/'holdout_evidence.json').read_text());verified_events=0
    for token in held['tokens']:
        c=token['creation'];raws={}
        for name in ['holdout-'+c['mint'],'DIAGNOSED:holdout-tail-'+c['mint']]:
            for row in rows_for(name)['rows']:raws[row['raw']['transaction']['signatures'][0]]=row['raw']
        for event in token['events']:
            regenerated=trades(raws[event['signature']],c['mint'])
            match=next(e for e in regenerated if (e['outer_index'],e['inner_index'])==(event['outer_index'],event['inner_index']))
            if any(event[k]!=v for k,v in match.items()):raise AssertionError('Holdout decoded event changed')
            verified_events+=1
    flags+=relationship_flags(held,addresses)
    if evaluate(held,addresses,flags)!=json.loads((ROOT/'holdout_results.json').read_text()):raise AssertionError('Holdout result reproduction changed')
    if independent_continuity(dev)!=json.loads((ROOT/'development_independent_continuity_v2.json').read_text()):raise AssertionError('Independent balance audit changed')
    return dict(**cache,development_reproduced=True,holdout_reproduced=True,holdout_events_redecoded=verified_events,
                strategy_lock_intact=True,shortlist_reproduced=True)

def consolidate():
    audit=reproduce();credits=credit_audit();dev=json.loads((ROOT/'development_evidence_final.json').read_text());held=json.loads((ROOT/'holdout_evidence.json').read_text())
    selected=json.loads((ROOT/'shortlist_final.json').read_text())['selected']
    scorecard=[]
    for split in ('development','holdout'):
        result=json.loads((ROOT/(split+'_results.json')).read_text())
        for rule in ('H1','H2','H3','momentum'):
            rows=[r for r in result['scenarios'] if r['hypothesis']==rule and r['size_lamports']==100000000 and r['delay_seconds']==15 and r['holding_seconds']==300]
            ts=[r for r in result['triggers'] if r['rule']==rule]
            scorecard.append(dict(partition=split,hypothesis=rule,observed_triggers=sum(bool(r['signature']) for r in ts),
                ordinary_matches=sum(r['ordinary_control_status']=='matched' for r in ts),
                simulated=sum(r['status']=='simulated' for r in rows),rejected=sum(r['status']=='rejected' for r in rows),
                unavailable=sum(r['status']=='unavailable' for r in rows),no_trigger=sum(r['status']=='no_trigger' for r in rows)))
    signatures=set()
    for line in (ROOT/'credits.jsonl').read_text().splitlines():
        e=json.loads(line);capture=json.loads((ROOT/(e['request_key']+'.json')).read_text())
        for raw in capture['response']['result'].get('data',[]):signatures.add(raw['transaction']['signatures'][0])
    summary=dict(edge='NO_EDGE_VALIDATED',generated_at=stamp(),credits=credits,offline_verification=audit,
        unique_captured_signatures=len(signatures),scorecard=scorecard,
        development_token_count=len(dev['tokens']),holdout_token_count=len(held['tokens']),
        wallet_count=len(selected),new_public_mappings=0,
        holdout_complete_activity_intervals=sum(t['coverage']['complete'] for t in held['tokens']),
        holdout_first_twelve_proven=False,automations='PAUSED',execution_enabled=False,
        declared_deviations=['All hypotheses use the frozen first-five-minute observation scope.',
            'A post-lock coverage-only driver filled diagnosed tails without changing the frozen decoder/strategy. Do not label this a pristine end-to-end preregistered holdout.',
            'No executable case exists under the validated regime; no return or slippage rejection was fabricated.'],
        hypotheses_decision={'H1':'Timing-observation candidate only; recurring wallet exits can precede every configured delay. No executable advantage established.',
                             'H2':'Unsupported: zero observed holdout convergence; dependency coverage incomplete.',
                             'H3':'Unsupported: one development trigger and zero observed holdout triggers; no execution edge established.'})
    save_new(ROOT/'public_amount_check.json',public_amount_check());save_new(ROOT/'holdout_wallet_behavior.json',wallet_behavior(held,selected))
    save_new(ROOT/'summary.json',summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    import sys
    print(json.dumps(reproduce(),indent=2)) if '--verify-only' in sys.argv else consolidate()
