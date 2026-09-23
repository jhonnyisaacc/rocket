"""Offline evidence panels; selection is independent of subsequent returns."""
import json
from collections import Counter,defaultdict
from statistics import median
from deep_session import ROOT, MANIFEST, SEEDS, save_new
from deep_evidence import rows_for,trades,VERSION
from continuation_accounting import activity
from pilot_decode import validate_trade,trade_instructions
from pilot_model import Fees
from pilot_decode import instructions

def order(e):return (e['slot'],e['transaction_index'],e['outer_index'],e['inner_index'])

def build_partition(split):
    panel=json.loads((ROOT/(split+'_cohort_v2.json')).read_text());result=[]
    for creation in panel['selected']:
        summary=rows_for(split+'-'+creation['mint']);events=[];failures=[];validation=Counter()
        for row in summary['rows']:
            raw=row['raw']
            try:
                for e in trades(raw,creation['mint']):
                    e.update(source_capture=row['source_capture'],retrieved_at=row['retrieved_at'],available_at=None,
                             age_seconds=e['timestamp']-creation['timestamp'],creator_self=e['economic_owner'] in (creation['creator'],creation['user']),
                             transaction_fee_lamports=raw['meta']['fee'])
                    # Reuse the old validator without weakening its fee or state guards.
                    try:
                        ix=next(i for i in trade_instructions(raw) if i['outer_index']==e['outer_index'] and i['inner_index']==e['inner_index'])
                        validate_trade(raw,e,ix,creation['bonding_curve'])
                        e['legacy_execution_supported']=True;validation['passed']+=1
                    except (ValueError,KeyError,StopIteration) as exc:
                        e['legacy_execution_supported']=False;e['execution_limitation']=str(exc) or 'Instruction schema differs';validation[e['execution_limitation']]+=1
                    events.append(e)
            except (ValueError,KeyError) as exc:
                failures.append(dict(signature=raw['transaction']['signatures'][0],timestamp=raw['blockTime'],reason=str(exc)))
        events.sort(key=order)
        first=[];seen=set()
        for e in events:
            if not e['economic_verified'] or not e['is_buy'] or e['creator_self'] or e['age_seconds']>300:continue
            if e['economic_owner'] not in seen:
                seen.add(e['economic_owner']);first.append(e)
            if len(first)==5:break
        result.append(dict(creation=creation,events=events,decode_failures=failures,
            coverage={k:v for k,v in summary.items() if k!='rows'},first_five_buyers=first,
            execution_validation=dict(validation),failed_transactions=summary['failed']))
    return dict(partition=split,decoder_version=VERSION,tokens=result)

def shortlist(partition):
    candidates=defaultdict(list)
    for token in partition['tokens']:
        for e in token['first_five_buyers']:candidates[e['economic_owner']].append(e)
    ranked=[dict(address=address,distinct_tokens=len({e['mint'] for e in es}),median_entry_age=median(e['age_seconds'] for e in es),
                 evidence=[dict(mint=e['mint'],signature=e['signature'],age_seconds=e['age_seconds']) for e in es],
                 public_identity=None,identity_available_at=None) for address,es in candidates.items()]
    ranked.sort(key=lambda r:(-r['distinct_tokens'],r['median_entry_age'],r['address']))
    return dict(selected=ranked[:8],excluded=ranked[8:],selection_uses_returns=False,
                limitation='First verified buyers; unresolved earlier routed buyers may affect true buyer rank. Development selection is retrospective.')

def seeds():
    out=[]
    for name,address in SEEDS.items():
        coverage=rows_for('seed-'+name);rows=[]
        for item in coverage['rows']:
            row=activity(item['raw'],address)
            row.update(source_capture=item['source_capture'],retrieved_at=item['retrieved_at'])
            rows.append(row)
        out.append(dict(name=name,address=address,coverage={k:v for k,v in coverage.items() if k!='rows'},rows=rows,
                        counts=dict(Counter(r['classification'] for r in rows)),
                        owner_network_fees_lamports=sum(r['owner_paid_fee_lamports'] for r in rows),
                        portfolio_pnl=None,opening_inventory_unknown=True))
    return out

def relationship_flags(partition,addresses):
    flags=[];seen=set();selected=set(addresses)
    for token in partition['tokens']:
        for item in rows_for(partition['partition']+'-'+token['creation']['mint'])['rows']:
            raw=item['raw']
            if raw['meta']['err'] is not None:continue
            signature=raw['transaction']['signatures'][0]
            if signature in seen:continue
            seen.add(signature)
            for outer,inner,ix in instructions(raw):
                p=ix.get('parsed',{})
                if not isinstance(p,dict) or ix.get('program')!='system' or p.get('type')!='transfer':continue
                info=p['info'];a=info.get('source');b=info.get('destination')
                if a!=b and a in selected and b in selected:
                    flags.append(dict(wallets=sorted([a,b]),source=a,destination=b,lamports=info['lamports'],
                        order=[raw['slot'],raw['transactionIndex'],outer,inner],event_time=raw['blockTime'],
                        signature=signature,reason='Direct transfer observed in bounded token evidence; not proof of common ownership'))
    return flags

if __name__=='__main__':
    p=build_partition('development');s=shortlist(p)
    save_new(ROOT/'development_evidence.json',p);save_new(ROOT/'shortlist_development.json',s)
    save_new(ROOT/'seed_activity.json',seeds())
    print(json.dumps(dict(tokens=len(p['tokens']),shortlist=s['selected']),indent=2))
