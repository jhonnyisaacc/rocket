"""Decode the published TradeEvent prefix; validate it against cached balances.

IDL source: https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/idl/pump.json
Inspected 2026-09-18. Only the fixed prefix through creator_fee is decoded;
remaining version-dependent bytes are preserved by length, never guessed.
"""
import base64
import json
import re
import struct
from decode_cached_history import ROOT

PUMP='6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
DISC=bytes([189,219,127,211,78,230,97,238])

def b58(raw):
    alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    value=int.from_bytes(raw,'big');out=''
    while value:
        value,r=divmod(value,58);out=alphabet[r]+out
    return '1'*(len(raw)-len(raw.lstrip(b'\0')))+out

def decode(data):
    if data[:8]!=DISC:return None
    if len(data)<225:raise ValueError('short TradeEvent prefix')
    offset=8
    def take(n):
        nonlocal offset
        part=data[offset:offset+n];offset+=n;return part
    def u64():return struct.unpack('<Q',take(8))[0]
    result={'mint':b58(take(32)),'sol_amount':u64(),'token_amount':u64()}
    flag=take(1)[0]
    if flag not in (0,1):raise ValueError('invalid bool')
    result.update(is_buy=bool(flag),user=b58(take(32)),timestamp=struct.unpack('<q',take(8))[0])
    for field in ('virtual_sol_reserves','virtual_token_reserves','real_sol_reserves','real_token_reserves'):
        result[field]=u64()
    result['fee_recipient']=b58(take(32))
    result['fee_basis_points']=u64();result['fee']=u64()
    result['creator']=b58(take(32))
    result['creator_fee_basis_points']=u64();result['creator_fee']=u64()
    result['unparsed_tail_bytes']=len(data)-offset
    # Current published extension, decode only when the complete fixed section
    # through buyback_fee is present; leave shareholder/quote extensions raw.
    if len(data)>=offset+37:
        track=take(1)[0]
        if track not in (0,1):raise ValueError('invalid track_volume')
        result['track_volume']=bool(track)
        for field in ('total_unclaimed_tokens','total_claimed_tokens','current_sol_volume'):
            result[field]=u64()
        result['last_update_timestamp']=struct.unpack('<q',take(8))[0]
        length=struct.unpack('<I',take(4))[0]
        if length>64 or len(data)<offset+length+33:raise ValueError('unsupported event extension')
        result['ix_name']=take(length).decode('utf8')
        flag=take(1)[0]
        if flag not in (0,1):raise ValueError('invalid mayhem bool')
        result['mayhem_mode']=bool(flag)
        for field in ('cashback_fee_basis_points','cashback','buyback_fee_basis_points','buyback_fee'):
            result[field]=u64()
        result['unparsed_tail_bytes']=len(data)-offset
    return result

def events(raw):
    if raw['meta']['err'] is not None:return []
    stack=[];out=[]
    for line in raw['meta'].get('logMessages',[]):
        match=re.match(r'Program (\w+) invoke \[\d+\]',line)
        if match:stack.append(match[1]);continue
        if re.match(r'Program \w+ (success|failed:)',line):
            if stack:stack.pop()
            continue
        if line.startswith('Program data: ') and stack and stack[-1]==PUMP:
            parsed=decode(base64.b64decode(line.split(': ',1)[1],validate=True))
            if parsed:out.append(parsed)
    return out

def main():
    summaries=[]
    for name in ('losing_cycle_market','winner_entry_curve'):
        capture=json.loads((ROOT/(name+'.json')).read_text());reserve=capture['request']['params'][0]
        output=[]
        for raw in capture['response']['result']['data']:
            ev=events(raw)
            for e in ev:
                meta=raw['meta'];mint=e['mint']
                def balance(field,owner):
                    return sum(int(b['uiTokenAmount']['amount']) for b in meta.get(field,[]) if b.get('owner')==owner and b['mint']==mint)
                e['signature']=raw['transaction']['signatures'][0];e['slot']=raw['slot']
                e['single_trade_event']=len(ev)==1
                e['timestamp_matches']=e['timestamp']==raw['blockTime']
                e['real_token_reserve_matches_post']=e['real_token_reserves']==balance('postTokenBalances',reserve)
                e['token_account_minus_event_real_reserve_raw']=balance('postTokenBalances',reserve)-e['real_token_reserves']
                change=balance('postTokenBalances',e['user'])-balance('preTokenBalances',e['user'])
                e['user_token_delta_matches']=change==(e['token_amount'] if e['is_buy'] else -e['token_amount'])
                output.append(e)
        (ROOT/(name+'_state_events.jsonl')).write_text(''.join(json.dumps(e)+'\n' for e in output))
        summaries.append({'cache':name,'events':len(output),'single_event_rows':sum(e['single_trade_event'] for e in output),
                          'timestamp_matches':sum(e['timestamp_matches'] for e in output),
                          'real_token_reserve_matches':sum(e['real_token_reserve_matches_post'] for e in output),
                          'user_token_matches':sum(e['user_token_delta_matches'] for e in output),
                          'reserve_offsets_raw':sorted({e['token_account_minus_event_real_reserve_raw'] for e in output}),
                          'observed_fee_bps':sorted({(e['fee_basis_points'],e['creator_fee_basis_points']) for e in output})})
    (ROOT/'curve_state_event_summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    print(json.dumps(summaries,indent=2))

if __name__=='__main__':main()
