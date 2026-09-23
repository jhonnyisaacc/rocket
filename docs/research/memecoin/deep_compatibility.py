"""Diagnostic quote arithmetic is not permission to simulate an unsupported regime."""
from collections import Counter
import json
from deep_session import ROOT,save_new
from deep_analysis import build_partition
from deep_evidence import rows_for
from pilot_model import Fees,pre_state,buy_exact_input,buy_exact_output,sell,post_state
from pilot_decode import balances

def diagnose(partition):
    records=[]
    for token in partition['tokens']:
        raw_by_sig={r['raw']['transaction']['signatures'][0]:r['raw'] for r in rows_for('development-'+token['creation']['mint'])['rows']}
        for e in token['events']:
            result=dict(mint=e['mint'],signature=e['signature'],instruction=e['instruction_name'],mayhem=e['mayhem_mode'],holder_rewards_bps=e['holder_rewards_bps'])
            f=Fees(e['fee_basis_points'],e['creator_fee_basis_points'],e['cashback_fee_basis_points'],e['buyback_fee_basis_points'])
            try:
                state=pre_state(e)
                q=buy_exact_input(state,e['first_argument'],f) if 'exact' in e['instruction_name'] else buy_exact_output(state,e['first_argument'],f) if e['is_buy'] else sell(state,e['first_argument'],f)
                result['quote_matches']=(q['gross'],q['tokens'])==(e['sol_amount'],e['token_amount'])
                result['quote_delta_lamports']=q['gross']-e['sol_amount']
                fee=f.amounts(e['sol_amount']);result['known_fee_fields_match']=all(fee[a]==e[b] for a,b in [('protocol','fee'),('creator','creator_fee'),('cashback','cashback'),('buyback','buyback_fee')])
            except ValueError as exc:result['quote_error']=str(exc)
            raw=raw_by_sig[e['signature']]
            try:
                pre=balances(raw,e['reserve'],e['mint'],'pre');post=balances(raw,e['reserve'],e['mint'],'post');sign=1 if e['is_buy'] else -1
                result['native_reserve_delta_matches']=(post[0]-pre[0],post[1]-pre[1])==(sign*e['sol_amount'],-sign*e['token_amount'])
            except ValueError as exc:result['reserve_error']=str(exc)
            result['admitted_for_replay']=False
            result['reasons']=['September historical fee configuration and transitions not validated','Native/WSOL instruction compatibility requires independent reserve-state proof']
            if e['mayhem_mode']:result['reasons'].append('Mayhem mode outside validated regime')
            if e['holder_rewards_bps']:result['reasons'].append('Holder-reward semantics outside validated regime')
            records.append(result)
    return dict(status='unsupported',records=records,counts=dict(Counter((str(r.get('quote_matches'))+' quote / '+str(r.get('native_reserve_delta_matches'))+' native') for r in records)),
                conclusion='Matching quote arithmetic alone is not independent execution validation. No fitted rounding correction or fee assumption admitted.')

if __name__=='__main__':
    result=diagnose(build_partition('development'));save_new(ROOT/'compatibility_diagnostics.json',result)
    print(json.dumps(result['counts']))
