"""Separate surviving creation funding from same-transaction closures.

This is a transaction-boundary deposit audit, not lifetime rent or PnL.
"""
import json
from decode_cached_history import ROOT

def inspect(raw, owner):
    meta=raw['meta']
    if meta['err'] is not None: return []
    keys=[k['pubkey'] for k in raw['transaction']['message']['accountKeys']]
    ins=raw['transaction']['message']['instructions']+[i for g in meta.get('innerInstructions',[]) for i in g['instructions']]
    closed={i['parsed']['info']['account'] for i in ins if isinstance(i.get('parsed'),dict) and i['parsed'].get('type')=='closeAccount'}
    token_accounts={keys[b['accountIndex']]:b for b in meta.get('postTokenBalances',[]) if b.get('owner')==owner}
    rows=[]
    for i in ins:
        p=i.get('parsed',{})
        if not isinstance(p,dict) or p.get('type') not in ('createAccount','createAccountWithSeed'):continue
        v=p['info']
        if v.get('source')!=owner:continue
        account=v['newAccount']; idx=keys.index(account); post=meta['postBalances'][idx]
        rows.append({'signature':raw['transaction']['signatures'][0],'account':account,
                     'funding_lamports':v['lamports'],'post_lamports':post,'closed_in_transaction':account in closed,
                     'owner_token_account_at_end':account in token_accounts,
                     'mint':token_accounts.get(account,{}).get('mint'),
                     'funding_equals_end_balance':v['lamports']==post,
                     'classification':'closed_or_zero_at_end' if account in closed or post==0 else 'surviving_owner_token_account' if account in token_accounts else 'other_surviving_account'})
    return rows

def main():
    c=json.loads((ROOT/'historical_cohort_sample.json').read_text())
    rows=[v for r in c['response']['result']['data'] for v in inspect(r,c['address'])]
    groups={k:{'records':sum(r['classification']==k for r in rows),'gross_funding_lamports':sum(r['funding_lamports'] for r in rows if r['classification']==k)} for k in sorted({r['classification'] for r in rows})}
    result={'new_api_calls':0,'groups':groups,'records':rows,'limitations':'End-of-transaction balances only. Later refunds, account ownership control and rent exemptions are not inferred; do not add gross funding to profit.'}
    (ROOT/'account_deposit_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(groups,indent=2))

if __name__=='__main__':main()
