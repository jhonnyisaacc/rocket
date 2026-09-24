"""Diagnostic realized reserve-ratio probes; no simulated fills or returns."""
import json
from decimal import Decimal
from decode_cached_history import ROOT

WSOL='So11111111111111111111111111111111111111112'

def main():
    reports=[]
    for venue in ('curve','amm'):
        label='winner_entry_'+venue
        manifest=json.loads((ROOT/(label+'_manifest.json')).read_text())
        capture=json.loads((ROOT/(label+'.json')).read_text())
        anchor=manifest['anchor']; owner=anchor['reserve_authority']; mint=anchor['mint']
        trades=[];failures=0
        for raw in capture['response']['result']['data']:
            meta=raw['meta']
            if meta['err'] is not None:failures+=1;continue
            def delta(token):
                return sum(sign*int(b['uiTokenAmount']['amount']) for sign,f in ((-1,'preTokenBalances'),(1,'postTokenBalances')) for b in meta.get(f,[]) if b.get('owner')==owner and b['mint']==token)
            base=delta(mint)
            keys=[k['pubkey'] for k in raw['transaction']['message']['accountKeys']]
            quote=delta(WSOL) if venue=='amm' else meta['postBalances'][keys.index(owner)]-meta['preBalances'][keys.index(owner)]
            if not base or quote*base>=0:continue
            trades.append({'signature':raw['transaction']['signatures'][0],'time':raw['blockTime'],
                           'ratio':str(abs(Decimal(quote)/Decimal(base)/Decimal(1000)))})
        match=next((r for r in trades if r['signature']==anchor['signature']),None)
        probes=[]
        for delay in (5,15,30):
            candidates=[r for r in trades if r['time']>=anchor['block_time']+delay]
            first=min((r['time'] for r in candidates),default=None)
            vals=[Decimal(r['ratio']) for r in candidates if r['time']==first]
            probes.append({'delay_seconds':delay,'first_observed_time':first,'observations':len(vals),
                           'change_min_pct':str((min(vals)/Decimal(match['ratio'])-1)*100) if vals and match else None,
                           'change_max_pct':str((max(vals)/Decimal(match['ratio'])-1)*100) if vals and match else None})
        reports.append({'venue':venue,'records':len(capture['response']['result']['data']),'failures':failures,
                        'opposing_flows':len(trades),'anchor_matched':match is not None,'probes':probes})
        (ROOT/(label+'_ratios.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in trades))
    result={'reports':reports,'limitations':'Selected winning case; not out-of-sample. Ratios are realized exchanges of different sizes/directions, not executable quotes. No transaction ordering, counterfactual price impact, fees or actual feed latency modeled. No follower return.'}
    (ROOT/'winner_entry_delay_probes.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
