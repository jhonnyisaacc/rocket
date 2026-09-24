"""Reconcile frozen public fills without upgrading conditional social identity."""
import json
import datetime as dt
import hashlib
from decimal import Decimal,ROUND_HALF_UP
from collections import defaultdict
from pilot_capture import OUT,BASE
from decode_cached_history import decode
from continuation_capture import load_capture,summarize_chain
from continuation_session import ROOT
from continuation_accounting import transfers,USDC
from pilot_discovery import MINT

CANDIDATE='FPLXEqws2rKy4k8B2tARTGV632fYCnPqxEktVMKfJ2H9'
CASES=[
 {'signature':'51rmSHLwVyGSXXXnTPteK5SQDbfcMRY6CHzQ6SHJ5eALscpDUmngpj1jicKmev4g1CCJPWxiyxSfuyfJtmP65sbT',
  'displayed_usd':'5530.57','minute_start':1790014980,'route_input_raw':5530574000,
  'owner_debit_raw':5555000000,'token_credit_raw':59403380080,
  'route_destination':'FzvRbXDdrsYVMa9KohXyQytWNAZAo4PsF8yujDH7KCfG'},
 {'signature':'48xDRdwKbcSDcTRXcUnZEuv85TaMKaXqJWWnxV5XLniw69qvpsUqfYU5HV3qdrWN8kdEr5sPv86HMa1D1TNcwpEx',
  'displayed_usd':'5530.03','minute_start':1790014980,'route_input_raw':5530029499,
  'owner_debit_raw':5555000000,'token_credit_raw':59186426653,
  'route_destination':'EPUHjseXG3izk3MVUJ1PcyWT9xeBhtAnq8gUpq3j8Uni'},
 {'signature':'paMXs6P9kbv7xr5PFYWZHy2fHiWRmHvDUmSNZtJdfUJbLPbKaUDk5fgSei4eDyESqa9ZgFKnCkBYQQg8U6ydksg',
  'displayed_usd':'9956.03','minute_start':1790015040,'route_input_raw':9956028800,
  'owner_debit_raw':10000000000,'token_credit_raw':105271465038,
  'route_destination':'2Y7HATmn9aJBcxCskE5V2U2epmjvkZmB51zTJBbhj4cU',
  'intermediate_account':'8XrtGP8RG33AnrN2yJ6H3gnXPNQ3dYXKqM72bpzhcsd6',
  'intermediate_input_raw':9964000000,'intermediate_separate_raw':7971200}
]

def money(raw):return str((Decimal(raw)/Decimal(1000000)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))

def verify_display_offset(evidence):
    bracket=[dt.datetime.fromisoformat(x.replace('Z','+00:00')).timestamp() for x in evidence['observation_utc_bracket']]
    if bracket[1]<bracket[0] or bracket[1]-bracket[0]>60:raise ValueError('Invalid clock bracket')
    anchors=evidence['anchors']
    if len(anchors)<2:raise ValueError('Insufficient independent time anchors')
    supported=[]
    for offset in evidence['candidate_offset_minutes']:
        matches=[]
        for anchor in anchors:
            local=dt.datetime.fromisoformat(anchor['absolute_local']).replace(tzinfo=dt.timezone.utc).timestamp()
            implied_utc=local-offset*60
            age_range=(bracket[0]-implied_utc,bracket[1]-implied_utc)
            rendered_age=anchor['relative_minutes']*60;tolerance=evidence['rounding_tolerance_seconds']
            matches.append(age_range[0]<=rendered_age+tolerance and age_range[1]>=rendered_age-tolerance)
        if all(matches):supported.append(offset)
    return {'supported_offset_minutes':supported,
            'frozen_offset_corroborated':supported==[evidence['frozen_offset_minutes']],
            'method':'Independent UTC clock versus paired visible absolute/relative UI times; quarter-hour offset candidates',
            'precision':'minute-scale corroboration, not exact seconds or browser configuration audit',
            'source':'fomo_time_evidence.json','chain_times_used_for_offset_selection':False}

def adjudicate_identity(matches,timezone_verified=False,explicit_public_wallet=False):
    if explicit_public_wallet:return {'status':'admitted_explicit_public_wallet','reason':'Explicit public linkage'}
    eligible=[m for m in matches if m.get('amount_reconciled') and m.get('owner_signed')
              and m.get('time_in_frozen_window') and m.get('successful') and m.get('logs_truncated') is False
              and m.get('unique_direct_input_match_in_frozen_window') is True]
    if not timezone_verified:
        return {'status':'unavailable','reason':'UI timezone remains inferred; conditional amount matches are not admitted identity',
                'otherwise_eligible_distinct_matches':len({m['signature'] for m in eligible})}
    if len({m['signature'] for m in eligible})<2:
        return {'status':'unavailable','reason':'Fewer than two distinct fully reconciled public fills'}
    if len({m['owner'] for m in eligible})!=1:
        return {'status':'unavailable','reason':'Conflicting candidate owners'}
    return {'status':'admitted_two_transaction_matches','owner':eligible[0]['owner'],
            'admitted_signatures':[m['signature'] for m in eligible],
            'reason':'Two distinct public fills reconcile; not proof of skill, legal identity or exclusivity'}

def build_panel():
    coverage=json.loads((ROOT/'cate_resumed_coverage.json').read_text())
    rows={};inventory=[]
    for interval in coverage['intervals']:
        captures=[load_capture(next(p for p in (ROOT/(key+'.json'),OUT/(key+'.json')) if p.exists()))
                  for key in interval['source_captures']]
        chain=summarize_chain(captures);inventory.append({k:v for k,v in chain.items() if k!='rows'})
        for item in chain['rows']:rows[item['raw']['transaction']['signatures'][0]]=item
    matches=[]
    for case in CASES:
        item=rows[case['signature']];raw=item['raw'];ownerrow=decode(raw,CANDIDATE);tx=transfers(raw)
        deltas={d['mint']:d['raw_delta'] for d in ownerrow['token_deltas']}
        outgoing=[t for t in tx if t['mint']==USDC and t['source_owner']==CANDIDATE and t['destination_owner']!=CANDIDATE]
        incoming=[t for t in tx if t['mint']==USDC and t['destination_owner']==CANDIDATE and t['source_owner']!=CANDIDATE]
        route=[t for t in tx if t['mint']==USDC and t['amount_raw']==case['route_input_raw'] and t['destination']==case['route_destination']]
        extra=[];intermediate_ok=True
        if 'intermediate_account' in case:
            mid=case['intermediate_account']
            mid_in=[t for t in tx if t['mint']==USDC and t['destination']==mid]
            mid_out=[t for t in tx if t['mint']==USDC and t['source']==mid]
            intermediate_ok=(sum(t['amount_raw'] for t in mid_in)==case['intermediate_input_raw']
                and sum(t['amount_raw'] for t in mid_out)==case['intermediate_input_raw']
                and len(route)==1 and route[0]['source']==mid)
            extra=[t for t in mid_out if t not in route]
        amount_ok=(len(route)==1 and intermediate_ok
            and deltas.get(USDC)==-case['owner_debit_raw'] and deltas.get(MINT)==case['token_credit_raw']
            and sum(t['amount_raw'] for t in outgoing)-sum(t['amount_raw'] for t in incoming)==case['owner_debit_raw']
            and money(case['route_input_raw'])==case['displayed_usd'])
        matches.append(dict(case,owner=CANDIDATE,event_time=raw['blockTime'],slot=raw['slot'],
            owner_signed=ownerrow['owner_is_signer'],successful=raw['meta']['err'] is None,
            time_in_frozen_window=case['minute_start']<=raw['blockTime']<case['minute_start']+60,
            logs_truncated=any('truncat' in x.lower() for x in raw['meta'].get('logMessages',[])),
            amount_reconciled=amount_ok,route_input_display_rounded=money(case['route_input_raw']),
            total_separate_quote_amount_raw=case['owner_debit_raw']-case['route_input_raw'],
            owner_quote_debits=outgoing,owner_quote_credits=incoming,route_transfer=route,
            intermediate_separate_transfers=extra,source_capture=item['source_capture'],
            retrieved_at=item['retrieved_at'],available_at=None,
            limitations=['Public UI dollar/USDC numerical correspondence, not an independently priced USD oracle.',
                         'Fee-like recipient roles are not verified. No insider or performance inference.']))
    public=json.loads((ROOT/'fomo_public_evidence.json').read_text())
    # Challenge the selected pair against every other signer in the complete
    # frozen windows. Selection is not based on the candidate's subsequent PnL.
    for match in matches:
        competitors=[]
        for item in rows.values():
            raw=item['raw']
            if raw['meta']['err'] is not None or not match['minute_start']<=raw['blockTime']<match['minute_start']+60:continue
            tx=None
            for key in raw['transaction']['message']['accountKeys']:
                if not isinstance(key,dict) or not key.get('signer'):continue
                owner=key['pubkey'];flow=decode(raw,owner);ds={d['mint']:d['raw_delta'] for d in flow['token_deltas']}
                if ds.get(MINT,0)<=0 or ds.get(USDC,0)>=0:continue
                if tx is None:tx=transfers(raw)
                hits=[t for t in tx if t['mint']==USDC and t['source_owner']==owner
                      and t['destination_owner']!=owner and money(t['amount_raw'])==match['displayed_usd']]
                if hits:competitors.append({'owner':owner,'signature':flow['signature'],'matching_transfers':hits})
        match['direct_input_competitors']=competitors
        match['unique_direct_input_match_in_frozen_window']=(len(competitors)==1
            and competitors[0]['owner']==CANDIDATE and competitors[0]['signature']==match['signature'])
    timezone=verify_display_offset(json.loads((ROOT/'fomo_time_evidence.json').read_text()))
    admission=adjudicate_identity(matches,timezone['frozen_offset_corroborated'],public['explicit_wallet_available'])
    flows=[]
    for item in rows.values():
        raw=item['raw']
        if raw['meta']['err'] is not None:continue
        for key in raw['transaction']['message']['accountKeys']:
            if not isinstance(key,dict) or not key.get('signer'):continue
            row=decode(raw,key['pubkey']);ds={d['mint']:d['raw_delta'] for d in row['token_deltas']}
            if ds.get(MINT,0)>0 and ds.get(USDC,0)<=-1_000_000_000:
                flows.append({'signature':row['signature'],'owner':key['pubkey'],'event_time':raw['blockTime'],
                    'usdc_debit_raw':-ds[USDC],'cate_credit_raw':ds[MINT],'social_identity':None})
    return {'edge':'NO_EDGE_VALIDATED','public_profile':public['profile'],'candidate_wallet':CANDIDATE,
        'public_evidence_reference':'fomo_public_evidence.json','coverage':inventory,
        'public_source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                               for name in ('fomo_public_evidence.json','fomo_time_evidence.json')},
        'unique_transactions':len(rows),'failed_transactions':sum(i['raw']['meta']['err'] is not None for i in rows.values()),
        'conditional_fill_matches':matches,'identity_admission':admission,'timezone_crosscheck':timezone,
        'admitted_new_wallet_mappings':int(admission['status'].startswith('admitted')),
        'unattributed_large_buy_like_flows':sorted(flows,key=lambda r:(r['event_time'],r['signature'])),
        'historical_identity_available_at':None,
        'mapping_adjudicated_at':'2026-09-21T19:18:26Z',
        'prior_5000_usdc_candidate':'Not admitted; does not reconcile to the three frozen public amounts.',
        'other_frozen_candidates':'Rochaboyyyy and therear66 unchanged; no replacement or new profiles inspected.'}
