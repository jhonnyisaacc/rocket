"""Integer formula diagnostics from emitted post-state, not a replay backtest."""
import json
from collections import Counter
from decode_cached_history import ROOT

def main():
    results=[]
    for name in ('losing_cycle_market','winner_entry_curve'):
        rows=[json.loads(l) for l in (ROOT/(name+'_state_events.jsonl')).read_text().splitlines()]
        errors=Counter();fee_errors=Counter();tail=Counter()
        for e in rows:
            sol,tokens=e['sol_amount'],e['token_amount']
            vs,vt=e['virtual_sol_reserves'],e['virtual_token_reserves']
            expected=(vs-sol)*tokens//vt+1 if e['is_buy'] else (vs+sol)*tokens//vt
            errors[(e.get('ix_name','unknown'),sol-expected)]+=1
            fee_errors[e['fee']-((sol*e['fee_basis_points']+9999)//10000)]+=1
            tail[(e.get('cashback_fee_basis_points'),e.get('buyback_fee_basis_points'))]+=1
        results.append({'cache':name,'events':len(rows),'formula_differences':[{'instruction':k[0],'lamport_error':k[1],'count':v} for k,v in sorted(errors.items())],
                        'fee_ceil_errors':dict(fee_errors),'cashback_buyback_bps':[{'cashback':k[0],'buyback':k[1],'events':v} for k,v in tail.items()]})
    (ROOT/'curve_rounding_diagnostics.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
