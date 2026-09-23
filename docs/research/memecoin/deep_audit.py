"""Offline auditing/reporting only; cannot alter the locked strategy or shortlist."""
import hashlib
import json
from collections import Counter
from deep_session import ROOT,MANIFEST
from pilot_capture import BASE,Capture,digest
from deep_evidence import rows_for
from pilot_decode import key_strings

def balance_snapshot(raw,reserve,mint,side):
    keys=key_strings(raw)
    def observed(token):
        values=[int(b['uiTokenAmount']['amount']) for b in raw['meta'].get(side+'TokenBalances',[]) if b.get('owner')==reserve and b['mint']==token]
        return sum(values) if values else None
    return dict(native=raw['meta'][side+'Balances'][keys.index(reserve)],
        base=observed(mint),wrapped=observed('So11111111111111111111111111111111111111112'))

def independent_continuity(partition):
    checks=[]
    for token in partition['tokens']:
        c=token['creation'];rows=rows_for(partition['partition']+'-'+c['mint'])['rows']
        for prior,current in zip(rows,rows[1:]):
            a,b=prior['raw'],current['raw']
            ordered=(a['slot'],a['transactionIndex'])<(b['slot'],b['transactionIndex'])
            left=balance_snapshot(a,c['bonding_curve'],c['mint'],'post');right=balance_snapshot(b,c['bonding_curve'],c['mint'],'pre')
            known=[key for key in left if left[key] is not None and right[key] is not None]
            matching=all(left[key]==right[key] for key in known)
            status='observed_native_and_base_match' if ordered and matching and 'base' in known else 'missing_balance_evidence' if matching else 'observed_mismatch'
            checks.append(dict(mint=c['mint'],prior=a['transaction']['signatures'][0],next=b['transaction']['signatures'][0],
                ordered=ordered,balance_continuity=matching,status=status,observed_fields=known,previous_post=left,next_pre=right,
                method='Independent account pre/post balances, not reconstruction using the next trade amount'))
    return dict(checks=checks,counts=dict(Counter(c['status'] for c in checks)),
        limitation='Unreferenced token balances are unknown, never zero. These field checks do not establish virtual reserves or full execution compatibility.')

def credit_audit():
    ledger=[json.loads(s) for s in (ROOT/'credits.jsonl').read_text().splitlines()];bybucket={};records=0
    for entry in ledger:
        bucket=bybucket.setdefault(entry['bucket'],dict(requests=0,reserved_credits=0,successful_response_estimate=0,unresolved_requests=0))
        bucket['requests']+=1;bucket['reserved_credits']+=entry['reserved_credits']
        path=ROOT/(entry['request_key']+'.json')
        if not path.exists():bucket['unresolved_requests']+=1;continue
        c=json.loads(path.read_text());n=len(c['response']['result']['data']) if entry['request']['method']=='getTransactionsForAddress' else None
        estimate=max(10,10*((n+99)//100)) if n is not None else entry['reserved_credits']
        records+=n or 0;bucket['successful_response_estimate']+=estimate
    return dict(buckets=bybucket,requests=len(ledger),reserved_credits=sum(x['reserved_credits'] for x in bybucket.values()),
        successful_response_estimate=sum(x['successful_response_estimate'] for x in bybucket.values()),
        returned_records_before_cross_query_dedup=records,actual_provider_billing=None,
        pricing='10 credits per 100 returned full transactions rounded up; minimum 10. Reservations use maximum page size.',
        pricing_source='https://www.helius.dev/docs/rpc/gettransactionsforaddress')

def verify_offline():
    calls=[]
    def forbidden(r):calls.append(r);raise AssertionError('Network forbidden during reproduction')
    client=Capture(ROOT,config=json.loads(MANIFEST.read_text()),transport=forbidden)
    entries=[json.loads(s) for s in (ROOT/'credits.jsonl').read_text().splitlines()]
    for e in entries:
        if not (ROOT/(e['request_key']+'.json')).exists():continue
        r=e['request'];client.call(r['method'],r['params'],bucket=e['bucket'],purpose=e['purpose'])
    if calls:raise AssertionError('Offline reproduction attempted network')
    original=json.loads((ROOT/'baseline_hashes.json').read_text());failures=[]
    for name,expected in original.items():
        if name.startswith('data/') or name=='session_20260921_manifest.json':
            if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=expected:failures.append(name)
    if failures:raise AssertionError('Prior artifacts changed: '+str(failures))
    return dict(cache_requests=len(entries),new_network_requests=len(calls),prior_artifacts_preserved=True)

def wallet_behavior(partition,selected):
    output=[]
    for wallet in selected:
        observations=[]
        for token in partition['tokens']:
            events=[e for e in token['events'] if e['user']==wallet['address'] and e.get('token_owner_verified')]
            if not events:continue
            buys=[e for e in events if e['is_buy']];sells=[e for e in events if not e['is_buy']]
            observations.append(dict(mint=token['creation']['mint'],symbol=token['creation']['symbol'],
                first_buy_age=min((e['age_seconds'] for e in buys),default=None),first_sell_age=min((e['age_seconds'] for e in sells),default=None),
                bought_raw=sum(e['token_amount'] for e in buys),sold_raw=sum(e['token_amount'] for e in sells),
                events=[dict(signature=e['signature'],age=e['age_seconds'],is_buy=e['is_buy'],amount=e['token_amount']) for e in events],
                profit=None,scope='Observed token movements only; not complete inventory or realized profit'))
        output.append(dict(address=wallet['address'],observations=observations))
    return output
