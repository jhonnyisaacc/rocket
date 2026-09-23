"""Freeze a future chronological sample from baseline cache bounds, not returns."""
import datetime as dt
import hashlib
import json
from pilot_capture import BASE,stamp
from pilot_decode import key_strings
from pilot_replay import OWNER
from continuation_session import ROOT,save_new

def build_spec():
    baseline=json.loads((ROOT/'baseline_hashes.json').read_text());records={};sources=[]
    for relative,expected in baseline.items():
        if not relative.endswith('.json') or '/sources/' in relative:continue
        path=BASE/relative
        # Only original capture objects, not derived artifacts or new captures.
        capture=json.loads(path.read_text())
        if not isinstance(capture,dict) or 'response' not in capture or 'request' not in capture:continue
        result=capture['response'].get('result')
        if not isinstance(result,dict):continue
        raw_rows=result.get('data',[result] if 'transaction' in result else [])
        relevant=[]
        for raw in raw_rows:
            if 'transaction' not in raw or 'meta' not in raw:continue
            owned=any(b.get('owner')==OWNER for field in ('preTokenBalances','postTokenBalances') for b in raw['meta'].get(field,[]))
            if OWNER not in key_strings(raw) and not owned:continue
            if not isinstance(raw.get('blockTime'),int):raise ValueError('Unknown source-wallet event time')
            signature=raw['transaction']['signatures'][0]
            if signature in records and records[signature]!=raw['blockTime']:raise ValueError('Conflicting baseline time')
            records[signature]=raw['blockTime'];relevant.append(signature)
        if relevant:
            if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Baseline capture changed')
            sources.append({'path':relative,'sha256':expected,'source_wallet_records':len(relevant)})
    if not records:raise ValueError('Missing source-wallet cache bounds')
    latest=max(records.values());day=dt.datetime.fromtimestamp(latest,dt.timezone.utc).date()+dt.timedelta(days=1)
    start=dt.datetime.combine(day,dt.time(),dt.timezone.utc);end=start+dt.timedelta(days=1)
    old=json.loads((BASE/'session_20260921_manifest.json').read_text())
    return {'experiment':'chronological-native-curve-follower-feasibility-v1','frozen_at':stamp(),
        'edge':'NO_EDGE_VALIDATED','source_wallet':OWNER,'social_identity':None,
        'source_cache_latest_event_time':latest,'source_cache_latest_event_utc':dt.datetime.fromtimestamp(latest,dt.timezone.utc).isoformat(),
        'baseline_unique_source_wallet_records':len(records),'baseline_evidence':sources,
        'interval':{'gte':int(start.timestamp()),'lt':int(end.timestamp()),'start_utc':start.isoformat(),'end_utc':end.isoformat()},
        'selection':'First 20 qualifying source-authorized successful native-SOL Pump buy events in slot/transaction/instruction order; use all if fewer; zero is an explicit outcome.',
        'eligibility':['Source wallet signs and its token/native or wrapped-native flow can be reconciled to the economic purchase; an event user alone is insufficient.',
            'Identify native-SOL Pump venue from accounts and instruction/event layout, not token symbol.',
            'Known calibration mints are excluded before numbering eligible events.',
            'Do not exclude an otherwise eligible event for missing execution state, unsupported fee regime, migration after entry, failed simulated execution, or poor subsequent returns.',
            'Ambiguous source ordering or attribution prevents claiming a complete first-20 sample; preserve boundary failures instead of skipping forward.',
            'Retain an audit of non-native/AMM/failed/non-buy source records; do not substitute wallets or dates.'],
        'excluded_calibration_mints':list(old['fixtures'].values()),
        'split':{'development':'eligible events 1–10','holdout':'eligible events 11–20',
                 'short_sample':'No replacement events or date extension; report actual size of each split.'},
        'outcome_collection_this_session':False,'holdout_outcomes_inspected':False,
        'holdout_boundary':'Freeze selection signatures first; holdout market-state/outcome files must remain outside development replay. Any incidental outcome exposure invalidates untouched status and must be disclosed, not silently relabeled.',
        'primary_size_lamports':100000000,'sizes_lamports':[10000000,100000000,500000000],
        'primary_delay_seconds':15,'delays_seconds':[5,15,30],
        'holding_seconds_after_entry':60,'exit_submission_delay':'same as entry delay','slippage_bps':200,
        'availability':'Block-time scenarios only; historical available_at null.',
        'execution':'Existing validated native-curve historical-state approximation only; no retuning, retries, peak exits, or assumed migration fills.',
        'costs':'Reuse protocol accounting, locked deposits and sample-observed low/median/p95 network-cost scenarios; disclose unpriced inclusion costs.',
        'overlap':'Independent fixed-budget scenarios, not a cash-constrained portfolio; repeated mints/overlapping positions are dependent observations.',
        'statuses':['simulated','unavailable','rejected'],
        'controls':'No wallet-selection edge claim. Freeze matched momentum and independent-wallet control rules before their acquisition.',
        'next_acquisition_authorized_by_this_spec':False,
        'next_acquisition_prerequisite':'Separately approved bounded session; freeze call count and coverage budget for the complete day before dispatch.'}

if __name__=='__main__':
    spec=build_spec();save_new(ROOT/'next_experiment.json',spec)
    print(json.dumps({k:spec[k] for k in ('source_cache_latest_event_utc','interval','baseline_unique_source_wallet_records')},indent=2))
