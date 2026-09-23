"""Offline per-mint cashflow evidence, NOT full portfolio PnL or copy backtest."""
import json
from collections import defaultdict
from decode_cached_history import ROOT, decode

def main():
    capture = json.loads((ROOT / 'historical_cohort_sample.json').read_text())
    owner = capture['address']
    groups = defaultdict(list)
    ambiguous = []
    for raw in capture['response']['result']['data']:
        row = decode(raw, owner)
        # Failed attempts can have no token delta; retain their referenced mints.
        mints = {b['mint'] for f in ('preTokenBalances', 'postTokenBalances')
                 for b in raw['meta'].get(f, []) if b.get('owner') == owner}
        if len(mints) != 1:
            ambiguous.append(row['signature'])
            continue
        logs = raw['meta'].get('logMessages', [])
        row['buy_log'] = any('Instruction: Buy' in s for s in logs)
        row['sell_log'] = any('Instruction: Sell' in s for s in logs)
        row['account_creation_lamports'] = 0
        for group in raw['meta'].get('innerInstructions', []):
            for ins in group['instructions']:
                parsed = ins.get('parsed', {})
                if isinstance(parsed, dict) and parsed.get('type') == 'createAccount' and parsed.get('info', {}).get('source') == owner and raw['meta']['err'] is None:
                    row['account_creation_lamports'] += int(parsed['info']['lamports'])
        groups[next(iter(mints))].append(row)
    output = []
    for mint, rows in sorted(groups.items()):
        rows.sort(key=lambda r: (r['block_time'] or 0, r['slot'] or 0))
        successful = [r for r in rows if r['category'] != 'failed' and r['token_deltas']]
        inflows = [r for r in successful if any(d['raw_delta'] > 0 for d in r['token_deltas'])]
        outflows = [r for r in successful if any(d['raw_delta'] < 0 for d in r['token_deltas'])]
        net = sum(d['raw_delta'] for r in successful for d in r['token_deltas'])
        output.append({'chain':'solana','mint':mint,'inflows':len(inflows),'outflows':len(outflows),
                       'net_raw_tokens':net,'failed_attempts':sum(r['category']=='failed' for r in rows),
                       'observed_native_cashflow_lamports':sum(r['native_delta_lamports'] for r in rows),
                       'owner_paid_transaction_fees_lamports':sum(r['transaction_fee_lamports'] for r in rows if r['fee_payer']==owner),
                       'account_creation_lamports':sum(r['account_creation_lamports'] for r in rows),
                       'elapsed_seconds':successful[-1]['block_time']-successful[0]['block_time'] if successful else None,
                       'all_inflows_have_buy_log':bool(inflows) and all(r['buy_log'] for r in inflows),
                       'all_outflows_have_sell_log':bool(outflows) and all(r['sell_log'] for r in outflows),
                       'signatures':[r['signature'] for r in rows]})
    result={'edge':'NO_EDGE_VALIDATED','new_api_calls':0,'unassigned_records':len(ambiguous),
            'limitations':'Single cached page; not complete history. Per-mint attribution restricted to one owner mint per transaction. Native cashflow includes fees, rent, tips and other transfers; no extra fee subtraction. Failed attempts retained. No follower returns or win rate inferred.',
            'mint_groups':output}
    (ROOT/'observed_cycle_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
