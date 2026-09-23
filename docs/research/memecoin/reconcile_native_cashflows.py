"""Account for observed native flows; expose unexplained program balance changes.

Only successful parsed system transfers/creates execute. Fees count on failures.
Account closure amounts are not inferred from pre-balances (accounts can receive
funds inside the same transaction). Residuals are evidence gaps, not profit.
"""
import json
from collections import Counter
from decode_cached_history import ROOT, decode

SYSTEM = '11111111111111111111111111111111'

def reconcile(raw, owner):
    row = decode(raw, owner)
    meta = raw['meta']
    instructions = list(raw['transaction']['message']['instructions'])
    instructions += [i for g in meta.get('innerInstructions', []) for i in g['instructions']]
    movements, closes = [], []
    if meta['err'] is None:
        for ins in instructions:
            p = ins.get('parsed', {})
            if not isinstance(p, dict):
                continue
            info, kind = p.get('info', {}), p.get('type')
            if kind == 'closeAccount' and info.get('destination') == owner:
                closes.append(info['account'])
            if ins.get('programId') != SYSTEM or kind not in ('transfer', 'transferWithSeed', 'createAccount', 'createAccountWithSeed'):
                continue
            source = info.get('source')
            dest = info.get('destination', info.get('newAccount'))
            if owner not in (source, dest):
                continue
            value = int(info['lamports']) * (int(dest == owner)-int(source == owner))
            movements.append({'kind':kind,'source':source,'destination':dest,'signed_lamports':value})
    fee = row['transaction_fee_lamports'] if row['fee_payer'] == owner else 0
    explained = sum(m['signed_lamports'] for m in movements)-fee
    row.update({'parsed_native_movements':movements,'owner_paid_fee_lamports':fee,
                'unexplained_native_lamports':row['native_delta_lamports']-explained,
                'token_accounts_closed_to_owner':closes})
    row['owner_mints'] = sorted({b['mint'] for f in ('preTokenBalances','postTokenBalances')
                                for b in meta.get(f,[]) if b.get('owner') == owner})
    return row

def main():
    capture=json.loads((ROOT/'historical_cohort_sample.json').read_text())
    rows=[reconcile(r,capture['address']) for r in capture['response']['result']['data']]
    (ROOT/'native_reconciliation.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    summary={}
    for name,subset in [('all',rows),('previously_unassigned',[r for r in rows if len(r['owner_mints']) != 1])]:
        summary[name]={'records':len(subset),'exactly_reconciled':sum(r['unexplained_native_lamports']==0 for r in subset),
                       'native_delta_lamports':sum(r['native_delta_lamports'] for r in subset),
                       'owner_paid_fee_lamports':sum(r['owner_paid_fee_lamports'] for r in subset),
                       'unexplained_native_lamports':sum(r['unexplained_native_lamports'] for r in subset),
                       'closure_rows':sum(bool(r['token_accounts_closed_to_owner']) for r in subset)}
    summary['limitations']='Residuals include direct program-owned lamport changes and account closures. They are not trading PnL. No economic counterparty labels inferred.'
    (ROOT/'native_reconciliation_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
