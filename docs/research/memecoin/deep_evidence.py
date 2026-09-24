"""Strict creation evidence and economic-owner checks, independent of returns."""
import base64
import json
import re
import struct
from collections import Counter
from deep_session import ROOT, MANIFEST, PUMP, save_new
from continuation_capture import load_capture, summarize_chain
from pilot_decode import instructions, unbase58, strict_events, trade_instructions, NATIVE
from decode_curve_state_events import b58
from continuation_accounting import transfers

VERSION='deep-evidence-2-september12'
IDL=json.loads((ROOT/'sources/pump_september_idl.json').read_text())
IXS={bytes(i['discriminator']):i for i in IDL['instructions']}
TYPES={x['name']:x['type'] for x in IDL['types']}
EVENTS={bytes(x['discriminator']):x['name'] for x in IDL['events']}

def parse_value(data,offset,typ):
    if isinstance(typ,str):
        if typ=='pubkey':
            if offset+32>len(data):raise ValueError('Short pubkey')
            return b58(data[offset:offset+32]),offset+32
        if typ=='string':
            n,offset=parse_value(data,offset,'u32')
            if n>4096 or offset+n>len(data):raise ValueError('Invalid string')
            return data[offset:offset+n].decode(),offset+n
        formats={'u8':'B','bool':'B','u16':'H','u32':'I','u64':'Q','i64':'q'}
        fmt='<'+formats[typ];size=struct.calcsize(fmt)
        v=struct.unpack_from(fmt,data,offset)[0]
        if typ=='bool' and v not in (0,1):raise ValueError('Invalid bool')
        return (bool(v) if typ=='bool' else v),offset+size
    if 'vec' in typ:
        n,offset=parse_value(data,offset,'u32')
        if n>64:raise ValueError('Oversized vector')
        out=[]
        for _ in range(n):v,offset=parse_value(data,offset,typ['vec']);out.append(v)
        return out,offset
    if 'defined' in typ:return parse_struct(data,offset,TYPES[typ['defined']['name']])
    raise ValueError('Unsupported field type')

def parse_struct(data,offset,definition):
    out={}
    for field in definition['fields']:out[field['name']],offset=parse_value(data,offset,field['type'])
    return out,offset

def event_payloads(raw):
    if raw['meta']['err'] is not None:return []
    logs=raw['meta'].get('logMessages')
    if not logs or any('truncat' in x.lower() for x in logs):raise ValueError('Truncated or absent logs')
    stack=[];out=[]
    for line in logs:
        m=re.fullmatch(r'Program (\w+) invoke \[(\d+)\]',line)
        if m:
            if int(m[2])!=len(stack)+1:raise ValueError('Invocation depth')
            stack.append(m[1])
        elif (m:=re.match(r'Program (\w+) (success|failed:)',line)):
            if m[2]!='success' or not stack or stack.pop()!=m[1]:raise ValueError('Failed or ambiguous invocation')
        elif line.startswith('Program data: ') and stack and stack[-1]==PUMP:
            out.append(base64.b64decode(line[14:],validate=True))
    if stack:raise ValueError('Unclosed invocation')
    return out

def creations(raw):
    create_ix=[]
    for outer,inner,ix in instructions(raw):
        if ix.get('programId')!=PUMP or 'data' not in ix:continue
        definition=IXS.get(unbase58(ix['data'])[:8])
        if definition and definition['name'] in ('create','create_v2'):
            create_ix.append((outer,inner,dict(zip([a['name'] for a in definition['accounts']],ix['accounts']))))
    if not create_ix or raw['meta']['err'] is not None:return []
    events=[]
    for payload in event_payloads(raw):
        if EVENTS.get(payload[:8])!='CreateEvent':continue
        e,end=parse_struct(payload,8,TYPES['CreateEvent'])
        if end!=len(payload):raise ValueError('Unsupported creation layout')
        matches=[(o,i,a) for o,i,a in create_ix if a.get('mint')==e['mint'] and a.get('bonding_curve')==e['bonding_curve'] and a.get('user')==e['user']]
        if len(matches)!=1 or e['timestamp']!=raw['blockTime']:raise ValueError('Ambiguous creation identity or time')
        if e['quote_mint']!=NATIVE or e['virtual_quote_reserves']!=e['virtual_sol_reserves']:continue
        o,i,a=matches[0]
        if not isinstance(raw.get('transactionIndex'),int):raise ValueError('Missing transaction order')
        e.update(slot=raw['slot'],transaction_index=raw['transactionIndex'],outer_index=o,inner_index=i,
                 signature=raw['transaction']['signatures'][0],decoder_version=VERSION)
        events.append(e)
    if len(events)!=len(create_ix):raise ValueError('Missing or unsupported creation event')
    return events

def rows_for(name):
    coverage=json.loads((ROOT/'queries'/(name+'.coverage.json')).read_text())
    return summarize_chain([load_capture(ROOT/(key+'.json')) for key in coverage['source_captures']])

def trades(raw,mint):
    decoded=[]
    for payload in event_payloads(raw):
        if EVENTS.get(payload[:8])!='TradeEvent':continue
        e,end=parse_struct(payload,8,TYPES['TradeEvent'])
        if end!=len(payload):raise ValueError('Unsupported trade layout')
        if e['mint']!=mint:continue
        if e['quote_mint']!=NATIVE or (e['quote_amount'],e['virtual_quote_reserves'],e['real_quote_reserves'])!=(e['sol_amount'],e['virtual_sol_reserves'],e['real_sol_reserves']):raise ValueError('Non-native or inconsistent quote')
        if e['timestamp']!=raw['blockTime']:raise ValueError('Trade time mismatch')
        candidates=[]
        for o,i,ix in instructions(raw):
            if ix.get('programId')!=PUMP or 'data' not in ix:continue
            d=unbase58(ix['data']);definition=IXS.get(d[:8])
            if not definition or definition['name'] not in ('buy','buy_v2','buy_exact_sol_in','buy_exact_quote_in_v2','sell','sell_v2'):continue
            accounts=dict(zip([a['name'] for a in definition['accounts']],ix['accounts']))
            if accounts.get('mint',accounts.get('base_mint'))==mint and accounts.get('user')==e['user']:
                candidates.append((o,i,accounts,definition['name'],d))
        if len(candidates)!=1:raise ValueError('Ambiguous trade instruction')
        o,i,accounts,name,data=candidates[0]
        signers={k['pubkey'] for k in raw['transaction']['message']['accountKeys'] if isinstance(k,dict) and k.get('signer')}
        owner=e['user'];flows=transfers(raw)
        net=sum(t['amount_raw']*((t.get('destination_owner')==owner)-(t.get('source_owner')==owner)) for t in flows if t['mint']==mint)
        expected=e['token_amount']*(1 if e['is_buy'] else -1)
        wsol='So11111111111111111111111111111111111111112'
        reserve=accounts.get('bonding_curve');quote_reserve=accounts.get('associated_quote_bonding_curve')
        payments=[]
        for t in flows:
            if t['mint']!=wsol or t['outer_index']!=o:continue
            if e['is_buy'] and t.get('source_owner')==owner and t['destination']==quote_reserve:
                payments.append(t['amount_raw'])
            elif not e['is_buy'] and t.get('destination_owner')==owner and t['source']==quote_reserve:
                payments.append(t['amount_raw'])
        for oo,ii,ix in instructions(raw):
            p=ix.get('parsed',{})
            if oo!=o or not isinstance(p,dict) or ix.get('program')!='system' or p.get('type')!='transfer':continue
            info=p['info']
            if e['is_buy'] and info.get('source')==owner and info.get('destination')==reserve:payments.append(int(info['lamports']))
            elif not e['is_buy'] and info.get('source')==reserve and info.get('destination')==owner:payments.append(int(info['lamports']))
        # Native program-owned reserves can debit lamports directly on sells;
        # those remain unverified economic disposals here unless parsed evidence exists.
        expected_quote=e['sol_amount'] if e['is_buy'] else e['sol_amount']-e['fee']-e['creator_fee']-e['cashback']-e['holder_rewards']
        payment_verified=expected_quote>0 and sum(payments)==expected_quote
        economic=owner in signers and net==expected and payment_verified
        e.update(economic_owner=owner if economic else None,economic_verified=economic,
                 owner_reason='Signed exact token and quote movements' if economic else 'Routed, unsigned or unreconciled token/quote movements',
                 quote_payment_verified=payment_verified,observed_quote_payments=payments,
                 token_owner_verified=owner in signers and net==expected,
                 reserve=accounts.get('bonding_curve'),slot=raw['slot'],transaction_index=raw.get('transactionIndex'),
                 outer_index=o,inner_index=i,signature=raw['transaction']['signatures'][0],decoder_version=VERSION,
                 instruction_name=name,first_argument=struct.unpack_from('<Q',data,8)[0],second_argument=struct.unpack_from('<Q',data,16)[0])
        decoded.append(e)
    return decoded

def cohort(split):
    summary=rows_for(split+'-cohort');events=[];failures=[]
    for row in summary['rows']:
        raw=row['raw']
        try:
            for e in creations(raw):e.update(source_capture=row['source_capture'],retrieved_at=row['retrieved_at'],available_at=None);events.append(e)
        except (ValueError,KeyError,struct.error,UnicodeError) as exc:
            failures.append(dict(signature=raw['transaction']['signatures'][0],slot=raw['slot'],transaction_index=raw.get('transactionIndex'),reason=str(exc)))
    events.sort(key=lambda e:(e['slot'],e['transaction_index'],e['outer_index'],e['inner_index']))
    excluded=set(json.loads(MANIFEST.read_text())['excluded_mints']);seen=set();selected=[]
    for e in events:
        if e['mint'] in seen or e['mint'] in excluded:continue
        seen.add(e['mint']);selected.append(e)
        if len(selected)==12:break
    cutoff=(selected[-1]['slot'],selected[-1]['transaction_index']) if selected else (0,0)
    blockers=[f for f in failures if f['transaction_index'] is None or (f['slot'],f['transaction_index'])<=cutoff]
    proven=len(selected)==12 and not blockers and summary['last_event_time']>selected[-1]['timestamp']
    out=dict(partition=split,selected=selected,creation_failures=failures,first_twelve_proven=proven,
             coverage_complete=summary['complete'],records=summary['records'],selection_status='complete_prefix' if proven else 'partial',
             no_replacement=True)
    save_new(ROOT/(split+'_cohort_v2.json'),out)
    print(json.dumps(dict(partition=split,selected=len(selected),verified_creations=len(events),failures=Counter(f['reason'] for f in failures),first_twelve_proven=proven)))
    return out

if __name__=='__main__':
    import sys
    cohort(sys.argv[1])
