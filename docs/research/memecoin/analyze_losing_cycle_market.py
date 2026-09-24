"""Observed reserve exchange ratios; explicitly NOT executable follower returns."""
import json
from decimal import Decimal
from decode_cached_history import ROOT

def main():
    capture=json.loads((ROOT/'losing_cycle_market.json').read_text())
    reserve=capture['request']['params'][0]
    mint='435CfmvrJ4QtkVv4cZ1TbUa7rzrKKjvQJLMnvhTCpump'
    trades=[]
    failures=0
    for r in capture['response']['result']['data']:
        meta=r['meta']
        if meta['err'] is not None:
            failures+=1;continue
        keys=[k['pubkey'] for k in r['transaction']['message']['accountKeys']]
        ix=keys.index(reserve)
        sol=meta['postBalances'][ix]-meta['preBalances'][ix]
        token=sum(sign*int(b['uiTokenAmount']['amount']) for sign,field in ((-1,'preTokenBalances'),(1,'postTokenBalances')) for b in meta.get(field,[]) if b.get('owner')==reserve and b['mint']==mint)
        if not sol or not token or sol*token>=0:continue
        price=abs(Decimal(sol)/Decimal(10**9)/(Decimal(token)/Decimal(10**6)))
        trades.append({'signature':r['transaction']['signatures'][0],'block_time':r['blockTime'],'slot':r['slot'],
                       'side':'buy' if sol>0 else 'sell','reserve_sol_delta_lamports':sol,
                       'reserve_token_delta_raw':token,'observed_reserve_ratio_sol_per_token':str(price)})
    trades.sort(key=lambda r:(r['block_time'],r['slot']))
    anchor=next(r for r in trades if r['signature']=='2ABsKP8yRzJFvtsgHzs9Ak3mDszT3SFUo7J6L2ej32kCNVqui9EA7YkjLgCu9UH8pdPvR37z7zxyAsWu7umSdUCB')
    probes=[]
    for delay in (5,15,30):
        target=anchor['block_time']+delay
        candidates=[r for r in trades if r['block_time']>=target]
        first=min((r['block_time'] for r in candidates),default=None)
        matches=[r for r in candidates if r['block_time']==first]
        prices=[Decimal(r['observed_reserve_ratio_sol_per_token']) for r in matches]
        probes.append({'delay_seconds':delay,'target_time':target,'first_observed_time':first,'same_second_observations':len(matches),
                       'ratio_min':str(min(prices)) if prices else None,'ratio_max':str(max(prices)) if prices else None,
                       'change_vs_anchor_min_pct':str((min(prices)/Decimal(anchor['observed_reserve_ratio_sol_per_token'])-1)*100) if prices else None,
                       'change_vs_anchor_max_pct':str((max(prices)/Decimal(anchor['observed_reserve_ratio_sol_per_token'])-1)*100) if prices else None})
    result={'new_api_calls':0,'captured_records':len(capture['response']['result']['data']),'failed_records':failures,
            'opposing_reserve_flows':len(trades),'anchor':anchor,'delay_probes':probes,
            'limitations':'First 100 records only; window truncated. Ratios are realized reserve exchange amounts, not marginal quotes or follower fills. Same-second order unresolved, trade sizes/directions differ, no fee/slippage/latency-adjusted return. No follower PnL calculated.'}
    (ROOT/'losing_cycle_market_ratios.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in trades))
    (ROOT/'losing_cycle_delay_probes.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
