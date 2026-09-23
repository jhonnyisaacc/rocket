"""Fail-closed historical decoder and independently ordered evidence inventory.

The selected May-18 IDL describes the observed 60-byte extension exactly.
This is compatibility evidence, not a deployed-program binary attestation.
"""
import base64
import hashlib
import json
import re
import struct
from pathlib import Path
from decode_curve_state_events import decode, b58, PUMP, DISC
from pilot_capture import BASE, OUT, digest
from pilot_model import State, pre_state, post_state, continuous, buy_exact_output, buy_exact_input, sell, Fees

VERSION = 'pilot-decode-1-may18-idl'
OLD = BASE/'data'/'helius-pilot-2026-09-16'
NATIVE = '11111111111111111111111111111111'
IDL = json.loads((OUT/'sources'/'historical_pump_idl.json').read_text())
IXS = {bytes(i['discriminator']): i for i in IDL['instructions']}


def unbase58(value):
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    number = 0
    for char in value:
        number = number*58 + alphabet.index(char)
    return b'\0'*(len(value)-len(value.lstrip('1'))) + number.to_bytes((number.bit_length()+7)//8, 'big')


def strict_events(raw):
    if raw['meta']['err'] is not None:
        return []
    logs = raw['meta'].get('logMessages')
    if not logs or any('truncat' in x.lower() for x in logs):
        raise ValueError('Missing or truncated logs')
    stack, result = [], []
    for line in logs:
        match = re.fullmatch(r'Program (\w+) invoke \[(\d+)\]', line)
        if match:
            if int(match[2]) != len(stack)+1:
                raise ValueError('Ambiguous invocation depth')
            stack.append(match[1])
        elif (match := re.match(r'Program (\w+) (success|failed:)', line)):
            if match[2]=='failed:':
                raise ValueError('Failed invocation inside successful transaction')
            if not stack or stack.pop() != match[1]:
                raise ValueError('Unbalanced invocation logs')
        elif line.startswith('Program data: ') and stack and stack[-1] == PUMP:
            payload = base64.b64decode(line[14:], validate=True)
            if payload[:8] != DISC:
                continue
            event = decode(payload)
            if event['unparsed_tail_bytes'] != 60 or struct.unpack('<I', payload[-60:-56])[0] != 0:
                raise ValueError('Unsupported historical event layout')
            event.update(quote_mint=b58(payload[-56:-24]))
            event['quote_amount'], event['virtual_quote_reserves'], event['real_quote_reserves'] = struct.unpack('<QQQ', payload[-24:])
            if event['quote_mint'] != NATIVE:
                raise ValueError('Unsupported non-native quote')
            if (event['quote_amount'], event['virtual_quote_reserves'], event['real_quote_reserves']) != (event['sol_amount'], event['virtual_sol_reserves'], event['real_sol_reserves']):
                raise ValueError('Quote/native event mismatch')
            event['decoder_version'] = VERSION
            result.append(event)
    if stack:
        raise ValueError('Truncated invocation stack')
    return result


def instructions(raw):
    result = []
    for outer_index, instruction in enumerate(raw['transaction']['message']['instructions']):
        result.append((outer_index, 0, instruction))
        group = next((g for g in raw['meta'].get('innerInstructions', []) if g['index'] == outer_index), None)
        if group:
            result.extend((outer_index, j+1, i) for j, i in enumerate(group['instructions']))
    return result


def trade_instructions(raw):
    result = []
    for outer, inner, instruction in instructions(raw):
        if instruction.get('programId') != PUMP or 'data' not in instruction:
            continue
        data = unbase58(instruction['data'])
        definition = IXS.get(data[:8])
        if definition and definition['name'] in ('buy','buy_v2','buy_exact_sol_in','buy_exact_quote_in_v2','sell','sell_v2'):
            if len(data) < 24:
                raise ValueError('Short trade instruction')
            result.append(dict(name=definition['name'], first_argument=struct.unpack('<Q', data[8:16])[0],
                               second_argument=struct.unpack('<Q', data[16:24])[0], accounts=instruction['accounts'],
                               account_names=[a['name'] for a in definition['accounts']], outer_index=outer, inner_index=inner))
    return result


def key_strings(raw):
    return [k['pubkey'] if isinstance(k,dict) else k for k in raw['transaction']['message']['accountKeys']]


def balances(raw, reserve, mint, side):
    keys = key_strings(raw)
    if reserve not in keys:
        raise ValueError('Reserve absent from transaction')
    native = raw['meta'][side+'Balances'][keys.index(reserve)]
    token = sum(int(b['uiTokenAmount']['amount']) for b in raw['meta'].get(side+'TokenBalances', [])
                if b.get('owner') == reserve and b['mint'] == mint)
    return native, token


def validate_trade(raw, event, ix, reserve):
    state = pre_state(event)
    f = Fees(event['fee_basis_points'], event['creator_fee_basis_points'],
             event['cashback_fee_basis_points'], event['buyback_fee_basis_points'])
    if f != Fees() or event['mayhem_mode']:
        raise ValueError('Unvalidated fee regime')
    if reserve not in ix['accounts'] or event['mint'] not in ix['accounts']:
        raise ValueError('Wrong reserve or mint instruction')
    mapped = dict(zip(ix['account_names'], ix['accounts']))
    if mapped.get('bonding_curve') != reserve or mapped.get('user') != event['user']:
        raise ValueError('Instruction identity mismatch')
    if event['timestamp'] != raw['blockTime']:
        raise ValueError('Event/block time mismatch')
    if ix['name'] in ('buy_exact_sol_in','buy_exact_quote_in_v2'):
        quote = buy_exact_input(state, ix['first_argument'], f)
    elif event['is_buy']:
        quote = buy_exact_output(state, ix['first_argument'], f)
    else:
        quote = sell(state, ix['first_argument'], f)
    if quote['gross'] != event['sol_amount'] or quote['tokens'] != event['token_amount']:
        raise ValueError('Instruction quote does not reproduce observed fill')
    charges = f.amounts(event['sol_amount'])
    if (charges['protocol'],charges['creator'],charges['cashback'],charges['buyback']) != (event['fee'],event['creator_fee'],event['cashback'],event['buyback_fee']):
        raise ValueError('Fee arithmetic mismatch')
    before, after = balances(raw, reserve, event['mint'], 'pre'), balances(raw, reserve, event['mint'], 'post')
    sign = 1 if event['is_buy'] else -1
    if (after[0]-before[0], after[1]-before[1]) != (sign*event['sol_amount'], -sign*event['token_amount']):
        raise ValueError('Independent reserve balance delta mismatch')
    keys = key_strings(raw)
    # Protocol/buyback accounts may receive multiple transfers elsewhere; exact
    # net changes are evidence only when matching, never force unexplained deltas.
    recipient = event['fee_recipient']
    recipient_delta = raw['meta']['postBalances'][keys.index(recipient)]-raw['meta']['preBalances'][keys.index(recipient)]
    buyback_account = mapped.get('buyback_fee_recipient')
    if not buyback_account:
        # Legacy ix has trailing buyback account. Resolve by exact recorded
        # positive delta plus explicit instruction membership, not label guessing.
        candidates = [a for a in ix['accounts'] if a in keys and a != recipient and
                      raw['meta']['postBalances'][keys.index(a)]-raw['meta']['preBalances'][keys.index(a)] == charges['buyback']]
        buyback_account = candidates[0] if len(candidates)==1 else None
    cashback_account = mapped.get('user_volume_accumulator')
    if not cashback_account and ix['name']=='sell' and len(ix['accounts'])>len(ix['account_names']):
        # Pre-trade cashback README: accumulator is first remaining sell account.
        cashback_account=ix['accounts'][len(ix['account_names'])]
    if not cashback_account:
        candidates = [a for a in ix['accounts'] if a in keys and
                      raw['meta']['postBalances'][keys.index(a)]-raw['meta']['preBalances'][keys.index(a)] == charges['cashback']]
        cashback_account = candidates[0] if len(candidates)==1 else None
    def delta(account):
        return None if account is None else raw['meta']['postBalances'][keys.index(account)]-raw['meta']['preBalances'][keys.index(account)]
    funding=0;cashback_actions=[]
    for _,_,instruction in instructions(raw):
        parsed=instruction.get('parsed',{})
        if not isinstance(parsed,dict):parsed={}
        info=parsed.get('info',{})
        if instruction.get('program')=='system' and parsed.get('type') in ('createAccount','createAccountWithSeed') and info.get('newAccount')==cashback_account:
            funding+=info['lamports']
        if instruction.get('programId')==PUMP and 'data' in instruction:
            definition=IXS.get(unbase58(instruction['data'])[:8])
            if definition and definition['name'] in ('claim_cashback','close_user_volume_accumulator'):
                accounts=dict(zip([a['name'] for a in definition['accounts']],instruction['accounts']))
                if accounts.get('user_volume_accumulator')==cashback_account:
                    cashback_actions.append(definition['name'])
    if delta(cashback_account)==charges['cashback']:
        cashback_treatment='retained_cashback'
    elif delta(cashback_account) is not None and delta(cashback_account)-funding==charges['cashback']:
        cashback_treatment='retained_cashback_plus_separate_account_deposit'
    elif cashback_actions:
        cashback_treatment='claim_or_close_in_same_transaction; final_delta_not_gross_fee'
    else:
        cashback_treatment='unresolved_destination_accounting'
    return dict(quote_matches=True, fees_match=True, native_reserve_before=before[0], native_reserve_after=after[0],
                token_reserve_before=before[1], token_reserve_after=after[1],
                protocol_recipient=recipient, protocol_retained_delta=recipient_delta,
                protocol_destination_matches=recipient_delta==charges['protocol_retained'],
                buyback_recipient=buyback_account, buyback_delta=delta(buyback_account),
                buyback_destination_matches=delta(buyback_account)==charges['buyback'],
                cashback_recipient=cashback_account, cashback_delta=delta(cashback_account),
                cashback_destination_matches=delta(cashback_account)==charges['cashback'],
                cashback_account_creation_funding=funding,cashback_actions=cashback_actions,
                cashback_treatment=cashback_treatment)


def order_transactions(transactions, blocks):
    byslot={};ordered=[];exclusions=[]
    for transaction in transactions:
        byslot.setdefault(transaction['raw']['slot'],[]).append(transaction)
    for slot, rows in sorted(byslot.items()):
        successful=[t for t in rows if t['raw']['meta']['err'] is None]
        if len(successful)>1 and slot not in blocks:
            for t in successful:
                exclusions.append(dict(signature=t['raw']['transaction']['signatures'][0],slot=slot,
                                       event_time=t['raw']['blockTime'],source=t['source'],reason='Ambiguous same-slot ordering'))
            # Retain fee-only failed records even when successful ordering fails.
            rows=[t for t in rows if t['raw']['meta']['err'] is not None]
        positions={s:i for i,s in enumerate(blocks.get(slot,[]))}
        if len(positions)!=len(blocks.get(slot,[])):
            raise ValueError('Duplicate signatures in block ordering evidence')
        if slot in blocks and any(t['raw']['transaction']['signatures'][0] not in positions for t in successful):
            raise ValueError('Transaction missing from block ordering evidence')
        for t in sorted(rows,key=lambda t:positions.get(t['raw']['transaction']['signatures'][0],-1)):
            t=dict(t,transaction_index=positions.get(t['raw']['transaction']['signatures'][0]))
            ordered.append(t)
    return ordered,exclusions


def load_evidence(event_decoder=None):
    captures = []
    blocks = {}
    reserve_allowlist={json.loads((OLD/(name+'.json')).read_text())['request']['params'][0]
                       for name in ('losing_cycle_market','winner_entry_curve')}
    for path in [OLD/'losing_cycle_market.json', OLD/'winner_entry_curve.json', *sorted(OUT.glob('*.json'))]:
        capture = json.loads(path.read_text())
        if not isinstance(capture,dict):
            continue
        method = capture.get('request',{}).get('method')
        if method not in ('getTransactionsForAddress','getBlock'):
            continue
        if 'response_sha256' in capture and digest(capture['response']) != capture['response_sha256']:
            raise ValueError('Capture hash mismatch')
        if method == 'getBlock':
            result = capture['response']['result']
            if result:
                blocks[capture['request']['params'][0]] = result['signatures']
        else:
            if capture['request']['params'][0] not in reserve_allowlist:
                continue  # Discovery captures are not calibration market states.
            captures.append((path,capture))
    seen, transactions, inventory, exclusions = {}, [], [], []
    for path, capture in captures:
        rows = capture['response']['result']['data']
        inventory.append(dict(path=str(path.relative_to(BASE)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                              retrieved_at=capture.get('retrieved_at'), request=capture['request'], count=len(rows),
                              failed=sum(r['meta']['err'] is not None for r in rows),
                              first_time=min((r['blockTime'] for r in rows),default=None),last_time=max((r['blockTime'] for r in rows),default=None),
                              pagination_token_present=bool(capture['response']['result'].get('paginationToken')),
                              response_at_limit=len(rows)>=capture['request']['params'][1].get('limit',100)))
        reserve = capture['request']['params'][0]
        for raw in rows:
            signature = raw['transaction']['signatures'][0]
            identity = ('solana-mainnet',signature)
            if identity in seen:
                if seen[identity] != digest(raw):
                    raise ValueError('Conflicting duplicate signature')
                continue
            seen[identity] = digest(raw)
            transactions.append(dict(raw=raw,reserve=reserve,source=str(path.relative_to(BASE)),retrieved_at=capture.get('retrieved_at')))
    ordered,exclusions=order_transactions(transactions,blocks)
    decoded, failed = [], []
    for t in ordered:
        raw = t['raw'];signature=raw['transaction']['signatures'][0]
        if raw['meta']['err'] is not None:
            failed.append(dict(signature=signature,event_time=raw['blockTime'],fee_lamports=raw['meta']['fee'],source=t['source'],status='reverted',state_applied=False))
            continue
        try:
            ev = (event_decoder or strict_events)(raw); ix = trade_instructions(raw)
            if len(ev)!=1 or len(ix)!=1:
                raise ValueError('Unsupported non-single-trade transaction or migration')
            e = ev[0]
            checks = validate_trade(raw,e,ix[0],t['reserve'])
            e.update(signature=signature,slot=raw['slot'],transaction_index=t['transaction_index'],
                     instruction_order=[ix[0]['outer_index'],ix[0]['inner_index']], reserve=t['reserve'], program=PUMP,
                     instruction_name=ix[0]['name'],instruction_amount_argument=ix[0]['first_argument'],
                     instruction_limit_argument=ix[0]['second_argument'],
                     event_time=raw['blockTime'],retrieved_at=t['retrieved_at'],available_at=None,
                     source=t['source'],network_fee_lamports=raw['meta']['fee'],checks=checks,
                     economic_trader=None,attribution='event user only; not automatically economic trader')
            decoded.append(e)
        except (ValueError,KeyError,IndexError) as exc:
            exclusions.append(dict(signature=signature,slot=raw['slot'],event_time=raw['blockTime'],source=t['source'],reason=str(exc)))
    transitions = []
    for mint in sorted({e['mint'] for e in decoded}):
        rows = [e for e in decoded if e['mint']==mint]
        for previous,current in zip(rows,rows[1:]):
            a,b=previous['checks'],current['checks']
            actual_continuity=(a['native_reserve_after'],a['token_reserve_after']) == (b['native_reserve_before'],b['token_reserve_before'])
            # Independent pre-state: use the NEXT transaction's actual pre-account
            # balances and the PREVIOUS event's reserve/account offsets. No use of
            # the next fill amounts to manufacture its quote input state.
            independent=State(
                b['native_reserve_before']+previous['virtual_sol_reserves']-a['native_reserve_after'],
                b['token_reserve_before']+previous['virtual_token_reserves']-a['token_reserve_after'],
                b['native_reserve_before']+previous['real_sol_reserves']-a['native_reserve_after'],
                b['token_reserve_before']+previous['real_token_reserves']-a['token_reserve_after'])
            quote_function=(buy_exact_input if current['instruction_name'] in ('buy_exact_sol_in','buy_exact_quote_in_v2')
                            else buy_exact_output if current['is_buy'] else sell)
            try:
                predicted=quote_function(independent,current['instruction_amount_argument'])
                independent_quote_match=(predicted['gross'],predicted['tokens'])==(current['sol_amount'],current['token_amount'])
            except ValueError:
                independent_quote_match=False
            transitions.append(dict(mint=mint,previous=previous['signature'],next=current['signature'],
                                    emitted_virtual_and_real_continuity=continuous(previous,current),
                                    independent_account_balance_continuity=actual_continuity,
                                    independent_pre_state=independent.__dict__,
                                    independent_instruction_quote_matches=independent_quote_match,
                                    pass_all=actual_continuity and continuous(previous,current) and independent_quote_match))
    return dict(decoder_version=VERSION,inventory=inventory,events=decoded,failed=failed,
                exclusions=exclusions,transitions=transitions,unique_transactions=len(seen))


def main():
    evidence=load_evidence()
    (OUT/'decoded_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({k:len(evidence[k]) for k in ('inventory','events','failed','exclusions','transitions')}))
    print('continuity_failures',sum(not t['pass_all'] for t in evidence['transitions']))
    from collections import Counter
    print('exclusions',Counter(e['reason'] for e in evidence['exclusions']))
    print('destination_matches',{k:sum(e['checks'][k] for e in evidence['events']) for k in ('protocol_destination_matches','buyback_destination_matches','cashback_destination_matches')})


if __name__=='__main__':
    main()
