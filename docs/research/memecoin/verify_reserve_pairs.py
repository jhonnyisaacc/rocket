"""Verify opposing owner/reserve token flows from cached transaction metadata.

Native conservation is an accounting check, not independent price validation.
Reserve identity means token-account authority here, not verified PDA derivation.
"""
import json
from collections import defaultdict, Counter
from decode_cached_history import ROOT, decode

PUMP = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
AMM = 'pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA'
WSOL = 'So11111111111111111111111111111111111111112'

def inspect(raw, owner):
    row = decode(raw, owner)
    meta = raw['meta']
    keys = [k['pubkey'] for k in raw['transaction']['message']['accountKeys']]
    if meta['err'] is not None or len(row['token_deltas']) != 1:
        return None
    mint = row['token_deltas'][0]['mint']
    delta = row['token_deltas'][0]['raw_delta']
    balances = defaultdict(int)
    opening = defaultdict(int)
    closing = defaultdict(int)
    for sign, field in ((-1,'preTokenBalances'),(1,'postTokenBalances')):
        for b in meta.get(field,[]):
            if b['mint'] == mint:
                balances[b.get('owner')] += sign*int(b['uiTokenAmount']['amount'])
                (opening if sign == -1 else closing)[b.get('owner')] += int(b['uiTokenAmount']['amount'])
    candidates = [a for a,v in balances.items() if a and a != owner and v == -delta and a in keys]
    instructions = raw['transaction']['message']['instructions'] + [i for g in meta.get('innerInstructions',[]) for i in g['instructions']]
    pump_accounts = set(a for i in instructions if i.get('programId') == PUMP for a in i.get('accounts',[]))
    native = {k:meta['postBalances'][i]-meta['preBalances'][i] for i,k in enumerate(keys)}
    reserve = candidates[0] if len(candidates)==1 else None
    reserve_delta = native.get(reserve)
    amm_accounts = set(a for i in instructions if i.get('programId') == AMM for a in i.get('accounts',[]))
    reserve_wsol_delta = sum(sign*int(b['uiTokenAmount']['amount'])
                             for sign,field in ((-1,'preTokenBalances'),(1,'postTokenBalances'))
                             for b in meta.get(field,[]) if b.get('owner') == reserve and b['mint'] == WSOL) if reserve else 0
    return {'signature':row['signature'],'block_time':row['block_time'],'slot':row['slot'],'mint':mint,
            'owner_token_delta_raw':delta,'owner_opening_tokens_raw':opening[owner],
            'owner_closing_tokens_raw':closing[owner], 'reserve_authority':reserve,
            'reserve_in_pump_instruction':reserve in pump_accounts if reserve else False,
            'owner_is_signer':row['owner_is_signer'],
            'reserve_native_delta_lamports':reserve_delta,'owner_native_delta_lamports':row['native_delta_lamports'],
            'opposing_reserve_native_direction':reserve_delta is not None and reserve_delta*delta>0,
            'reserve_in_amm_instruction':reserve in amm_accounts if reserve else False,
            'reserve_wsol_delta_raw':reserve_wsol_delta,
            'quote_direction_pass':(reserve in pump_accounts and reserve_delta is not None and reserve_delta*delta>0) or (reserve in amm_accounts and reserve_wsol_delta*delta>0),
            'transaction_conserves_lamports':sum(native.values()) == -meta['fee'],
            'other_native_changes':[{'account':a,'delta_lamports':v} for a,v in native.items() if v and a not in (owner,reserve)],
            'fee_lamports':meta['fee']}

def main():
    capture=json.loads((ROOT/'historical_cohort_sample.json').read_text())
    rows=[v for r in capture['response']['result']['data'] if (v:=inspect(r,capture['address'])) is not None]
    groups=defaultdict(list)
    for r in rows: groups[r['mint']].append(r)
    summary=[]
    for mint,events in sorted(groups.items()):
        events.sort(key=lambda r:(r['block_time'],r['slot']))
        summary.append({'mint':mint,'events':len(events),'first_opening_tokens_raw':events[0]['owner_opening_tokens_raw'],
                        'last_closing_tokens_raw':events[-1]['owner_closing_tokens_raw'],
                        'all_reserve_pairs_pass':all(r['quote_direction_pass'] and r['transaction_conserves_lamports'] and r['owner_is_signer'] for r in events)})
    (ROOT/'reserve_pair_evidence.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    report={'records':len(rows),'unique_reserve_matches':sum(r['reserve_authority'] is not None for r in rows),
            'reserve_in_pump_instruction':sum(r['reserve_in_pump_instruction'] for r in rows),
            'all_conserve_lamports':all(r['transaction_conserves_lamports'] for r in rows),'groups':summary,
            'limitations':'Observed token authority and instruction membership, not independently derived PDA. Same-slot ordering not resolved. Zero opening/closing inventory applies to observed accounts; closed historical accounts and missing pages may remain. No follower execution prices.'}
    (ROOT/'reserve_pair_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
