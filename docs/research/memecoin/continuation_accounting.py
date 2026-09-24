"""Canonical wallet cash/activity accounting; no PnL or inferred identity."""
from collections import Counter
import json
from pilot_capture import BASE
from pilot_decode import instructions,key_strings
from decode_cached_history import decode
from reconcile_native_cashflows import reconcile
from continuation_capture import load_capture,summarize_chain
from continuation_session import ROOT,UNIPCS

USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
WSOL='So11111111111111111111111111111111111111112'
VERSION='continuation-accounting-2-observed-transient-closure'

def transient_wsol_refund(raw,account,owner):
    """Reconstruct observed in-transaction closure, never a future rent refund.

    Scope: zero opening/closing lamports, one explicit creation and closure,
    complete logs, parsed native movements and wrapped-native token transfers.
    """
    meta=raw['meta'];keys=key_strings(raw)
    if meta['err'] is not None or any('truncat' in x.lower() for x in meta.get('logMessages',[])):
        return None
    if token_accounts(raw).get(account,{}).get('mint')!=WSOL:return None
    index=keys.index(account)
    if meta['preBalances'][index]!=0 or meta['postBalances'][index]!=0:return None
    creates=[];closes=[];native_movements=[]
    for outer,inner,i in instructions(raw):
        p=i.get('parsed',{})
        if not isinstance(p,dict):
            if i.get('programId') in ('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA','11111111111111111111111111111111') and account in i.get('accounts',[]):return None
            continue
        info=p.get('info',{});kind=p.get('type');order=(outer,inner)
        if i.get('program')=='system':
            if kind in ('createAccount','createAccountWithSeed') and info.get('newAccount')==account:
                creates.append((order,int(info['lamports'])))
            elif kind in ('transfer','transferWithSeed'):
                value=int(info['lamports'])*(int(info.get('destination')==account)-int(info.get('source')==account))
                if value:native_movements.append((order,value))
        if kind=='closeAccount' and info.get('account')==account:
            if info.get('destination')!=owner:return None
            closes.append(order)
    if len(creates)!=1 or len(closes)!=1 or creates[0][0]>=closes[0]:return None
    if any(not creates[0][0]<order<closes[0] for order,_ in native_movements):return None
    native=sum(value for _,value in native_movements)
    flows=[t for t in transfers(raw) if account in (t['source'],t['destination'])]
    if any(t['mint']!=WSOL or not creates[0][0]<(t['outer_index'],t['inner_index'])<closes[0] for t in flows):return None
    wrapped_net=sum(t['amount_raw']*(int(t['destination']==account)-int(t['source']==account)) for t in flows)
    value=creates[0][1]+native+wrapped_net
    if value<0:return None
    return {'account':account,'destination':owner,'lamports':value,'creation_funding_lamports':creates[0][1],
            'parsed_native_net_excluding_creation_lamports':native,'wrapped_native_net_lamports':wrapped_net,
            'method':'Observed zero-boundary transient WSOL account conservation with explicit close destination',
            'future_refund_assumed':False}

def token_accounts(raw):
    keys=key_strings(raw);accounts={}
    for field in ('preTokenBalances','postTokenBalances'):
        for b in raw['meta'].get(field,[]):
            address=keys[b['accountIndex']]
            if address in accounts and accounts[address]['mint']!=b['mint']:
                raise ValueError('Token account mint changed')
            accounts[address]={'mint':b['mint'],'owner':b.get('owner'),'decimals':b['uiTokenAmount']['decimals']}
    for _,_,i in instructions(raw):
        parsed=i.get('parsed',{})
        if not isinstance(parsed,dict):continue
        info=parsed.get('info',{})
        if parsed.get('type') in ('initializeAccount','initializeAccount2','initializeAccount3'):
            address=info['account'];old=accounts.get(address,{})
            if old.get('mint',info['mint'])!=info['mint']:raise ValueError('Conflicting initialized mint')
            accounts[address]=dict(old,mint=info['mint'],owner=info['owner'])
    return accounts

def transfers(raw):
    """Only executed transfers; infer unchecked mint from observed token accounts."""
    if raw['meta']['err'] is not None:return []
    accounts=token_accounts(raw);result=[]
    for outer,inner,i in instructions(raw):
        p=i.get('parsed',{})
        if not isinstance(p,dict) or p.get('type') not in ('transfer','transferChecked'):continue
        if i.get('program') not in ('spl-token','spl-token-2022') and i.get('programId') not in (
            'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA','TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb'):continue
        info=p['info'];source=info['source'];dest=info['destination']
        mint=info.get('mint') or accounts.get(source,{}).get('mint') or accounts.get(dest,{}).get('mint')
        amount=int(info.get('amount',info.get('tokenAmount',{}).get('amount',0)))
        result.append({'source':source,'destination':dest,'mint':mint,'amount_raw':amount,
            'source_owner':accounts.get(source,{}).get('owner'),'destination_owner':accounts.get(dest,{}).get('owner'),
            'outer_index':outer,'inner_index':inner,'stack_height':i.get('stackHeight'),
            'authority':info.get('authority',info.get('multisigAuthority'))})
    return result

def activity(raw,owner,adjudications=()):
    row=reconcile(raw,owner);keys=key_strings(raw);meta=raw['meta'];accounts=token_accounts(raw)
    executed=transfers(raw);deltas={r['mint']:r['raw_delta'] for r in row['token_deltas']}
    known=next((a for a in adjudications if a['signature']==row['signature']),None)
    row.update(decoder_version=VERSION,event_time=row.pop('block_time'),available_at=None,
               native_delta_includes_owner_network_fee=True,network_fee_is_incremental_cost=False,
               state_applied=meta['err'] is None,executed_token_transfers=executed,
               fee_like_transfers=[],account_deposits=[],closure_refunds_recognized_lamports=0,
               economic_outcome=None,classification='unverified_activity')
    if meta['err'] is not None:
        row['classification']='failed_attempt'
        row['failure_attribution']='owner_signed' if row['owner_is_signer'] else 'related_account_reference_only; not owner trade'
        return row
    if known:
        proof=json.loads((BASE/'data'/'fomo-fill-adjudications.json').read_text())
        if owner!=proof['owner'] or not row['owner_is_signer'] or deltas.get(proof['quote_mint'])!=-known['quote_debit_raw'] or deltas.get(proof['mint'])!=known['token_credit_raw']:
            raise ValueError('Previously adjudicated fill no longer reconciles')
        quote_out=[t for t in executed if t['mint']==USDC and t['source_owner']==owner and t['destination_owner']!=owner]
        quote_in=[t for t in executed if t['mint']==USDC and t['destination_owner']==owner and t['source_owner']!=owner]
        if sum(t['amount_raw'] for t in quote_out)-sum(t['amount_raw'] for t in quote_in)!=known['quote_debit_raw']:
            raise ValueError('Known fill quote transfer conservation failed')
        fees=[]
        for value in known['separate_quote_transfers_raw']:
            matches=[t for t in quote_out if t['amount_raw']==value]
            if len(matches)!=1:raise ValueError('Ambiguous fee-like transfer')
            fees.append(dict(matches[0],role='fee_like_not_provider_verified',already_in_quote_debit=True))
        row.update(classification='verified_buy',verified_trade=True,fee_like_transfers=fees,
            routed_quote_input_raw=known['quote_debit_raw']-sum(known['separate_quote_transfers_raw']),
            total_quote_debit_raw=known['quote_debit_raw'],
            identity_evidence='data/fomo-fill-adjudications.json; two previously corroborated public fills')
    elif row['category']=='token_inflow_only':row['classification']='transfer_in_not_established_buy'
    elif row['category']=='token_outflow_only':row['classification']='transfer_out_not_established_sell'
    elif not deltas:row['classification']='no_owner_token_change'
    elif deltas.get(USDC,0)<0 and any(v>0 for m,v in deltas.items() if m!=USDC):row['classification']='buy_like_unverified'
    elif deltas.get(USDC,0)>0 and any(v<0 for m,v in deltas.items() if m!=USDC):row['classification']='sell_like_unverified'
    for _,_,i in instructions(raw):
        p=i.get('parsed',{})
        if not isinstance(p,dict):continue
        info=p.get('info',{})
        if i.get('program')=='system' and p.get('type') in ('createAccount','createAccountWithSeed'):
            account=info['newAccount']
            if accounts.get(account,{}).get('owner')!=owner:continue
            index=keys.index(account);pre=meta['preBalances'][index];post=meta['postBalances'][index]
            surviving=post>0
            mint=accounts[account]['mint']
            row['account_deposits'].append(dict(account=account,mint=mint,creation_payer=info['source'],
                funded_lamports=info['lamports'],pre_lamports=pre,post_lamports=post,survives_transaction=surviving,
                classification='surviving_account_cash_requirement' if surviving else 'transient_account_funding_not_retained_deposit',
                refundable_amount_claimed=None,not_an_additional_fee=True,
                note='WSOL account balance can include wrapped principal' if mint==WSOL else 'No future refund assumed'))
    refunds=[transient_wsol_refund(raw,account,owner) for account in row['token_accounts_closed_to_owner']]
    refunds=[r for r in refunds if r is not None]
    row['observed_closure_refunds']=refunds
    row['closure_refunds_recognized_lamports']=sum(r['lamports'] for r in refunds)
    row['unexplained_native_after_observed_closures_lamports']=row['unexplained_native_lamports']-row['closure_refunds_recognized_lamports']
    return row

def build_wallet_ledger():
    coverage=json.loads((ROOT/'unipcs_coverage.json').read_text())['intervals'][0]
    captures=[load_capture(ROOT/(key+'.json')) for key in coverage['source_captures']]
    chain=summarize_chain(captures)
    proof=json.loads((BASE/'data'/'fomo-fill-adjudications.json').read_text())
    rows=[]
    for item in chain['rows']:
        row=activity(item['raw'],UNIPCS,proof['fills'])
        row.update(source_capture=item['source_capture'],retrieved_at=item['retrieved_at'],
                   transaction_index=item['raw'].get('transactionIndex'),same_slot_order_asserted=item['raw'].get('transactionIndex') is not None)
        rows.append(row)
    net=Counter()
    for row in rows:
        for d in row['token_deltas']:net[d['mint']]+=d['raw_delta']
    return {'owner':UNIPCS,'decoder_version':VERSION,'coverage':coverage,'rows':rows,
        'classifications':dict(Counter(r['classification'] for r in rows)),
        'owner_paid_network_fee_lamports':sum(r['owner_paid_fee_lamports'] for r in rows),
        'all_referenced_transaction_fees_lamports':sum(r['transaction_fee_lamports'] for r in rows),
        'native_cash_change_lamports':sum(r['native_delta_lamports'] for r in rows),
        'token_net_changes_raw':dict(net),'economic_outcome':None,
        'limitations':['Five-minute provider-reported wallet/token-account reference coverage, not full portfolio history.',
            'Inbound receipts and related-account failures do not establish wallet trades.',
            'Transaction fees paid by another signer are not deducted from owner cash a second time.',
            'Fee-like transfer roles and any off-chain reimbursement remain unverified.',
            'Transfers, existing inventory, deposits and missing price marks prevent interpreting net cash as trading PnL.',
            'No AMM follower execution model enabled.']}
