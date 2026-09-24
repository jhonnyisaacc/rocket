"""Trailing-only frozen hypotheses, controls, and fail-closed scenario reporting."""
import hashlib
import json
from fractions import Fraction
from itertools import combinations,product
from collections import Counter
from deep_session import ROOT, MANIFEST, save_new
from deep_analysis import order,build_partition,shortlist,relationship_flags
from pilot_capture import stamp,BASE

def price(e):return Fraction(e['virtual_sol_reserves'],e['virtual_token_reserves'])

def ordinary(events,trigger,selected):
    eligible=[e for e in events if order(e)<order(trigger) and e['age_seconds']//60==trigger['age_seconds']//60
              and e['is_buy'] and e['economic_verified'] and not e['creator_self'] and e['economic_owner'] not in selected]
    return max(eligible,key=order) if eligible else None

def triggers(token,selected,flagged=(),exclude_related=False):
    events=token['events'];found={};declines=[]
    for i,e in enumerate(events):
        if not 0<=e['age_seconds']<=300:continue
        past=events[:i+1];t=e['timestamp'];recent=[x for x in past if t-60<=x['timestamp']<=t]
        earlier=[x for x in past if x['timestamp']<=t-60]
        if earlier and e['age_seconds']>=60 and price(e)>=price(earlier[-1])*Fraction(110,100):
            found.setdefault('momentum',e)
        preceding=[x for x in events[:i] if t-60<=x['timestamp']<=t]
        if preceding and price(e)<=max(map(price,preceding))*Fraction(90,100):declines.append(e)
        buy=e['is_buy'] and e['economic_verified'] and not e['creator_self'] and e['economic_owner'] in selected
        if not buy:continue
        found.setdefault('H1',e)
        recent_buyers={x['economic_owner'] for x in recent if x['is_buy'] and x['economic_verified'] and not x['creator_self'] and x['economic_owner'] in selected}
        pairs=list(combinations(sorted(recent_buyers),2))
        def independent(pair):
            return not any(set(f['wallets'])==set(pair) and tuple(f['order'])<=order(e) for f in flagged)
        pairs=[p for p in pairs if not exclude_related or independent(p)]
        if pairs:found.setdefault('H2',e)
        for decline in reversed(declines):
            if t-decline['timestamp']>60:break
            since=[x for x in past if order(x)>order(decline)]
            bought={x['economic_owner'] for x in since if x['is_buy'] and x['economic_verified'] and not x['creator_self'] and x['economic_owner'] in selected}
            for pair in pairs:
                if not set(pair)<=bought:continue
                # Signed token flows establish acquisition even where sale cash
                # proceeds are not yet independently reconstructed.
                net=sum(x['token_amount']*(1 if x['is_buy'] else -1) for x in since if x.get('token_owner_verified') and x['user'] in pair)
                if net>0:found.setdefault('H3',e)
    return found

def evaluate(partition,addresses,flags=()):
    m=json.loads(MANIFEST.read_text());rows=[];trigger_rows=[]
    for token in partition['tokens']:
        c=token['creation'];found=triggers(token,set(addresses),flags)
        sensitivity=triggers(token,set(addresses),flags,True)
        for rule in ('H1','H2','H3','momentum'):
            e=found.get(rule);control=ordinary(token['events'],e,set(addresses)) if e and rule!='momentum' else None
            trigger_rows.append(dict(mint=c['mint'],symbol=c['symbol'],rule=rule,
                signature=e['signature'] if e else None,age_seconds=e['age_seconds'] if e else None,
                ordinary_control=control['signature'] if control else None,
                ordinary_control_status='matched' if control else 'unmatched' if e else 'not_applicable',
                excluding_flagged_signature=sensitivity[rule]['signature'] if rule in sensitivity else None))
            for size,delay,hold in product(m['sizes_lamports'],m['delays_seconds'],m['holding_seconds']):
                complete=token['coverage']['complete'] and not token['decode_failures']
                status='unavailable' if e else ('no_trigger' if complete else 'unavailable')
                reason='September execution regime not validated' if e else ('No verified trigger in frozen observation window' if complete else 'Incomplete event evidence cannot establish no trigger')
                rows.append(dict(partition=partition['partition'],mint=c['mint'],symbol=c['symbol'],hypothesis=rule,size_lamports=size,
                    delay_seconds=delay,holding_seconds=hold,slippage_bps=200,status=status,reason=reason,
                    trigger_signature=e['signature'] if e else None,net_outcome_lamports=None,cash_required_lamports=None,
                    ordinary_control_status='unavailable_execution' if control else 'unmatched' if e else 'not_applicable',
                    historical_available_at=None,unpriced_components=['historical fee configuration','supported reserve transition','network inclusion','account cash requirements'],
                    exit_coverage_supported=False if hold==900 else None))
    return dict(partition=partition['partition'],triggers=trigger_rows,scenarios=rows,
                counts=dict(Counter(r['status'] for r in rows)),edge='NO_EDGE_VALIDATED',
                no_trigger_scope='No economically verified observed trigger; unresolved routing may conceal economic buyers.',
                counterfactual='Historical-state approximation only; no own-trade subsequent market reaction modeled.')

LOCK_FILES=['deep_session.py','deep_capture.py','deep_evidence.py','deep_analysis.py','deep_experiment.py','deep_compatibility.py','pilot_capture.py','pilot_model.py','pilot_decode.py','continuation_accounting.py','continuation_capture.py','decode_curve_state_events.py']
def implementation_hashes():
    return {name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in LOCK_FILES}

def freeze():
    p=build_partition('development');s=shortlist(p)
    addresses=[r['address'] for r in s['selected']];flags=relationship_flags(p,addresses)
    save_new(ROOT/'development_evidence_final.json',p);save_new(ROOT/'shortlist_final.json',s)
    save_new(ROOT/'relationship_flags.json',dict(flags=flags,coverage='Only direct transfers visible in sampled reserve transactions; absence does not establish independence'))
    save_new(ROOT/'development_results.json',evaluate(p,addresses,flags))
    save_new(ROOT/'holdout_lock.json',dict(frozen_at=stamp(),implementation_hashes=implementation_hashes(),
        shortlist_sha256=hashlib.sha256((ROOT/'shortlist_final.json').read_bytes()).hexdigest(),
        settings_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),holdout_outcomes_previously_accessed=False))

def verify_lock():
    lock=json.loads((ROOT/'holdout_lock.json').read_text())
    if lock['implementation_hashes']!=implementation_hashes():raise ValueError('Holdout implementation contamination')
    if lock['shortlist_sha256']!=hashlib.sha256((ROOT/'shortlist_final.json').read_bytes()).hexdigest():raise ValueError('Shortlist contamination')
    if lock['settings_sha256']!=hashlib.sha256(MANIFEST.read_bytes()).hexdigest():raise ValueError('Settings contamination')

if __name__=='__main__':freeze()
