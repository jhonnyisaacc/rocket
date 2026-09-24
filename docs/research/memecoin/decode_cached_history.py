"""Offline evidence ledger. No network, credentials, or trade execution.

Classifications describe balance directions, not proven swaps or profitability.
Raw quantities remain integers; native SOL changes include rent and fees.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'data' / 'helius-pilot-2026-09-16'


def decode(row, owner):
    meta = row['meta']
    message = row['transaction']['message']
    keys = [k['pubkey'] if isinstance(k, dict) else k for k in message['accountKeys']]
    balances, accounts, decimals = {}, set(), {}
    for sign, field in ((-1, 'preTokenBalances'), (1, 'postTokenBalances')):
        for b in meta.get(field) or []:
            if b.get('owner') != owner:
                continue
            mint = b['mint']
            accounts.add(keys[b['accountIndex']])
            decimals[mint] = b['uiTokenAmount']['decimals']
            balances[mint] = balances.get(mint, 0) + sign * int(b['uiTokenAmount']['amount'])
    balances = {m: v for m, v in balances.items() if v}
    instructions = list(message.get('instructions', []))
    instructions.extend(i for g in meta.get('innerInstructions') or [] for i in g['instructions'])
    transfers = []
    for instruction in instructions:
        parsed = instruction.get('parsed') or {}
        if not isinstance(parsed, dict) or parsed.get('type') not in ('transfer', 'transferChecked'):
            continue
        info = parsed.get('info', {})
        if info.get('source') in accounts or info.get('destination') in accounts:
            transfers.append({'program': instruction.get('programId'), 'type': parsed['type'],
                              'info': info, 'incoming': info.get('destination') in accounts,
                              'outgoing': info.get('source') in accounts})
    native = meta['postBalances'][keys.index(owner)] - meta['preBalances'][keys.index(owner)] if owner in keys else 0
    positive, negative = any(v > 0 for v in balances.values()), any(v < 0 for v in balances.values())
    if meta.get('err') is not None:
        category = 'failed'
    elif positive and negative:
        category = 'two_sided_token_flow_unverified'
    elif positive:
        category = 'token_inflow_with_native_outflow_unverified' if native < 0 else 'token_inflow_only'
    elif negative:
        category = 'token_outflow_with_native_inflow_unverified' if native > 0 else 'token_outflow_only'
    else:
        category = 'no_owner_token_change'
    return {'signature': row['transaction']['signatures'][0], 'block_time': row.get('blockTime'),
            'slot': row.get('slot'), 'owner': owner, 'category': category,
            'owner_is_signer': any(isinstance(k, dict) and k['pubkey'] == owner and k.get('signer') for k in message['accountKeys']),
            'native_delta_lamports': native, 'transaction_fee_lamports': meta.get('fee'),
            'fee_payer': keys[0], 'token_deltas': [{'mint': m, 'raw_delta': v, 'decimals': decimals[m]} for m, v in balances.items()],
            'parsed_owner_token_transfers': transfers, 'verified_trade': False}


def main():
    reports = {}
    for label in ('fomo_unipcs_candidate', 'historical_cohort_sample'):
        capture = json.loads((ROOT / (label + '.json')).read_text())
        rows = [decode(r, capture['address']) for r in capture['response']['result']['data']]
        (ROOT / (label + '_ledger.jsonl')).write_text(''.join(json.dumps(r) + '\n' for r in rows))
        reports[label] = {'records': len(rows), 'categories': dict(Counter(r['category'] for r in rows)),
                          'owner_signer_rows': sum(r['owner_is_signer'] for r in rows),
                          'rows_with_outgoing_token_transfer': sum(any(t['outgoing'] for t in r['parsed_owner_token_transfers']) for r in rows),
                          'rows_with_incoming_token_transfer': sum(any(t['incoming'] for t in r['parsed_owner_token_transfers']) for r in rows),
                          'verified_trades': 0}
    report = {'new_api_calls': 0, 'edge': 'NO_EDGE_VALIDATED', 'wallets': reports,
              'limitations': 'Partial historical pages. Parsed transfers may be incomplete. Directions do not prove swaps; no cost basis, execution price, or follower return inferred.'}
    (ROOT / 'ledger_summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
