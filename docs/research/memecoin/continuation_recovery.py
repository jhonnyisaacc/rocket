"""Opt-in recovery of ONE corroborated CPI event; strict decoder stays default."""
import base64
import copy
import hashlib
import json
import struct
from pilot_decode import (PUMP, DISC, NATIVE, VERSION, OUT, BASE, decode, b58,
    unbase58, instructions, trade_instructions, strict_events, load_evidence)

SIGNATURE='335cgm4nVceZ7h34CtcL9ZbAK1zB16pBSkeqq6mLhkGj8d7Fg4ThgZZGs7fU3z51apyaUcz31owmjP85ni4UrEQ8'
EVENT_TAG=bytes.fromhex('e445a52e51cb9a1d')
AUTHORITY='Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1'
RECOVERY_VERSION='continuation-cpi-1-scoped-adjacent-verified'

def recover_candidate(raw):
    if raw['transaction']['signatures'][0]!=SIGNATURE:
        raise ValueError('Recovery outside frozen signature scope')
    if raw['meta']['err'] is not None:
        raise ValueError('Cannot recover reverted event')
    logs=raw['meta'].get('logMessages') or []
    if not any('truncat' in x.lower() for x in logs):
        raise ValueError('Scoped recovery requires known truncated record')
    if any(' failed:' in line for line in logs):
        raise ValueError('Failed invocation in recovery record')
    trades=trade_instructions(raw)
    if len(trades)!=1:
        raise ValueError('Ambiguous trade instruction count')
    trade=trades[0];mapped=dict(zip(trade['account_names'],trade['accounts']))
    if mapped.get('event_authority')!=AUTHORITY or mapped.get('program')!=PUMP:
        raise ValueError('Wrong trade event authority or program')
    seq=instructions(raw);candidates=[]
    for outer,inner,ix in seq:
        if ix.get('programId')!=PUMP or 'data' not in ix:continue
        data=unbase58(ix['data'])
        if data[:8]==EVENT_TAG and data[8:16]==DISC:
            candidates.append((outer,inner,ix,data[8:]))
    if len(candidates)!=1:raise ValueError('Missing or ambiguous embedded trade events')
    outer,inner,ix,payload=candidates[0]
    if ix.get('accounts')!=[AUTHORITY] or outer!=trade['outer_index'] or inner<=trade['inner_index']:
        raise ValueError('Embedded event authority/order mismatch')
    parent=next(i for o,j,i in seq if (o,j)==(outer,trade['inner_index']))
    parent_depth=parent.get('stackHeight')
    if not isinstance(parent_depth,int) or ix.get('stackHeight')!=parent_depth+1:
        raise ValueError('Ambiguous embedded-event stack depth')
    between=[i for o,j,i in seq if o==outer and trade['inner_index']<j<inner]
    if any(not isinstance(i.get('stackHeight'),int) or i['stackHeight']<=parent_depth for i in between):
        raise ValueError('Embedded event not nested in selected trade')
    e=decode(payload)
    if e['unparsed_tail_bytes']!=60 or struct.unpack('<I',payload[-60:-56])[0]!=0:
        raise ValueError('Unsupported embedded historical layout')
    e['quote_mint']=b58(payload[-56:-24])
    e['quote_amount'],e['virtual_quote_reserves'],e['real_quote_reserves']=struct.unpack('<QQQ',payload[-24:])
    if e['quote_mint']!=NATIVE or (e['quote_amount'],e['virtual_quote_reserves'],e['real_quote_reserves'])!=(e['sol_amount'],e['virtual_sol_reserves'],e['real_sol_reserves']):
        raise ValueError('Unsupported embedded quote reserves')
    # A surviving log copy is corroboration, not the source of admission.
    log_copies=[]
    for line in logs:
        if line.startswith('Program data: '):
            data=base64.b64decode(line[14:],validate=True)
            if data[:8]==DISC:log_copies.append(data)
    if any(data!=payload for data in log_copies):
        raise ValueError('Conflicting log and embedded event payloads')
    e['decoder_version']=RECOVERY_VERSION
    e['recovery_provenance']={'kind':'instruction_embedded_self_cpi','outer_index':outer,
        'inner_index':inner,'stack_height':ix['stackHeight'],'event_authority':AUTHORITY,
        'payload_sha256':hashlib.sha256(payload).hexdigest(),'matching_surviving_log_copies':len(log_copies),
        'historical_idl_sha256':hashlib.sha256((OUT/'sources'/'historical_pump_idl.json').read_bytes()).hexdigest(),
        'admission':'provisional_until_independent_neighbors_pass',
        'reference':'https://www.anchor-lang.com/docs/features/events'}
    return [e]

def candidate_decoder(raw):
    if raw['transaction']['signatures'][0]==SIGNATURE:return recover_candidate(raw)
    return strict_events(raw)

def recovered_evidence():
    baseline=load_evidence()
    candidate=load_evidence(event_decoder=candidate_decoder)
    event=next((e for e in candidate['events'] if e['signature']==SIGNATURE),None)
    transitions=[t for t in candidate['transitions'] if SIGNATURE in (t['previous'],t['next'])]
    failures=[]
    if event is None:
        failures.extend(e['reason'] for e in candidate['exclusions'] if e['signature']==SIGNATURE)
    else:
        neighbors=[next(e for e in candidate['events'] if e['signature']==s)
                   for t in transitions for s in (t['previous'],t['next']) if s!=SIGNATURE]
        # Different slots are ordered by slot number; only same-slot neighbors
        # require independently captured block transaction positions.
        if any(n['slot']==event['slot'] and (n['transaction_index'] is None or event['transaction_index'] is None) for n in neighbors):
            failures.append('Missing material same-slot block ordering')
        from pilot_replay import coverage_intervals,covered
        if len(neighbors)!=2 or not covered(coverage_intervals(candidate,event['reserve']),
                                           min(n['event_time'] for n in neighbors),max(n['event_time'] for n in neighbors)):
            failures.append('Incomplete provider-reported adjacent interval coverage')
        if len(transitions)!=2 or not all(t['pass_all'] for t in transitions):
            failures.append('Independent adjacent state/quote corroboration failed')
        if not event['checks']['protocol_destination_matches'] or not event['checks']['buyback_destination_matches']:
            failures.append('Fee destinations not corroborated')
    report={'signature':SIGNATURE,'decoder_version':RECOVERY_VERSION,'status':'unavailable' if failures else 'recovered',
            'failures':failures,'neighbor_checks':transitions,'new_helius_credits':0}
    if failures:return baseline,report
    event['recovery_provenance']['admission']='independent_previous_and_next_state_checks_passed'
    candidate['decoder_version']=VERSION+'+'+RECOVERY_VERSION
    report['event']=copy.deepcopy(event)
    return candidate,report
