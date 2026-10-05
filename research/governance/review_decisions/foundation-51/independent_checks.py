"""Independent offline checks of preserved MOM-000 artifacts; no raw acquisition/scoring."""
import csv
import hashlib
import io
import json
import math
import pathlib
import sys
from collections import Counter
from datetime import UTC, datetime

from rocket.momentum.core import CandidateEvent, DAY, FOUR_HOURS, HOUR, LAG, interval_groups, spaced_events
import rocket.momentum.core as reviewed_core

ROOT = pathlib.Path(__file__).resolve().parent
DOC = ROOT / 'docs/research/momentum'

def read(path):
    return json.loads((DOC / path).read_text())

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def stamp(value):
    return int(datetime.fromisoformat(value).timestamp() * 1000)

def different(left, right):
    return [key for key, value in left.items() if not (
        math.isclose(value, right[key], rel_tol=1e-12, abs_tol=1e-12)
        if isinstance(value, float) and isinstance(right[key], float)
        else value == right[key])]

def components(events, days, start_delay):
    result = []
    end = None
    contacts = []
    for event in sorted(events, key=lambda e: e['data_cutoff']):
        start = event['data_cutoff'] + start_delay
        if end is None or start > end:
            result.append([])
        elif start == end:
            contacts.append({'cutoff_utc': datetime.fromtimestamp(event['data_cutoff']/1000, UTC).isoformat(), 'event_id': event['event_id']})
        result[-1].append(event['event_id'])
        end = max(end or 0, event['data_cutoff'] + days * DAY)
    return result, contacts

rows = read('results/EVENTS.json')
events = [r['event'] for r in rows]
diff = read('reconciliation/CANDIDATE_DIFF.json')
recon = read('reconciliation/RECONCILIATION.json')
f49 = read('reconciliation/PR49_FROZEN_CENSUS.json')
f50 = read('reconciliation/PR50_FROZEN_CENSUS.json')
census = read('results/CENSUS.json')
source = read('SOURCE_MANIFEST.json')
traces = read('reconciliation/DISCREPANT_BARRIER_TRACES.json')
tier = read('TIER_B_SOURCE_MANIFEST.json')
assert pathlib.Path(reviewed_core.__file__).resolve().is_relative_to(ROOT)
assert len(rows) == len(diff) == len(set(e['event_id'] for e in events)) == 354
assert events == sorted(events, key=lambda e: e['decision_time'])
assert all(e['decision_time'] == e['data_cutoff'] + LAG and e['data_cutoff'] % FOUR_HOURS == 0 for e in events)
assert all(e['event_id'] == digest({'cutoff':e['data_cutoff'], 'direction':e['direction'], 'generator':e['generator']}) for e in events)
label_fingerprint = digest([r['label'] for r in rows])
assert label_fingerprint == census['labels_fingerprint'] == f49['labels_fingerprint'] == recon['canonical_label_fingerprint']
original_counts, repaired_counts = Counter(), Counter()
max_error = {'sigma':0., 'scale':0., 'reference_price':0.}
for row, original in zip(diff, rows):
    e, lab = original['event'], original['label']
    assert row['event_id'] == e['event_id']
    assert row['decision_time'] == e['decision_time']
    assert stamp(row['cutoff_utc']) == e['data_cutoff']
    assert row['direction'] == ('UP' if e['direction'] == 1 else 'DOWN')
    assert row['globally_spaced'] == original['independent']
    assert row['canonical_reference_price'] == e['reference_price']
    assert row['canonical_scale_S'] == e['scale']
    assert row['canonical_sigma'] == e['scale'] / math.sqrt(42)
    assert all(lab[k] == v for k,v in row['canonical'].items())
    assert lab['horizon_days'] == 7 and lab['upper'] == 2 and lab['lower'] == 1
    assert lab['event_id'] == e['event_id'] and lab['contract'] == e['generator']
    assert lab['label_end'] == e['data_cutoff'] + 7 * DAY
    assert lab['available_at'] == lab['label_end'] + LAG
    raw_time = row['muse_original_resolution_hour_open']
    assert row['muse_original']['barrier_time'] == (None if raw_time is None else raw_time + HOUR)
    computed = different(row['canonical'], row['muse_original'])
    repaired = different(row['canonical'], row['muse_orientation_only'])
    assert set(computed) == set(row['discrepant_fields']) and set(repaired) == set(row['orientation_only_discrepant_fields'])
    original_counts.update(computed)
    repaired_counts.update(repaired)
    floored = dict(row['muse_orientation_only'])
    for k in ('mfe','mfe_normalized'):
        if floored[k] is not None:
            floored[k] = max(0., floored[k])
    assert different(row['canonical'], floored) == []
    for key, left, right in [('sigma',row['canonical_sigma'],row['muse_sigma']),('scale',row['canonical_scale_S'],row['muse_scale_S']),('reference_price',row['canonical_reference_price'],row['muse_reference_price'])]:
        max_error[key] = max(max_error[key], abs(left-right))
        assert math.isclose(left,right,rel_tol=1e-12,abs_tol=1e-12)
assert dict(original_counts) == recon['original_muse_field_discrepancy_counts']
assert dict(repaired_counts) == recon['orientation_only_remaining_discrepancy_counts']
spaced = []
next_time = -1
for e in events:
    if e['decision_time'] >= next_time:
        spaced.append(e['event_id'])
        next_time = e['decision_time'] + 14 * DAY
assert len(spaced) == 107
assert spaced == [r['event']['event_id'] for r in rows if r['independent']]
assert spaced == [e.event_id for e in spaced_events([CandidateEvent(**e) for e in events])]
primary_counts = {}
for direction in ('UP','DOWN'):
    selected = [r for r in diff if r['direction']==direction and r['globally_spaced']]
    canonical_counts = dict(Counter(r['canonical']['outcome'] for r in selected))
    muse_counts = dict(Counter('CONTINUES' if r['muse_original']['outcome'].startswith('CONTINUES_') else r['muse_original']['outcome'] for r in selected))
    assert canonical_counts == recon['primary_counts'][direction]['canonical']
    assert muse_counts == recon['primary_counts'][direction]['muse_original']
    assert muse_counts.get('CONTINUES') == f50[direction]['continues']
    primary_counts[direction] = {'canonical':canonical_counts,'muse_original':muse_counts}
assert census['gate'] == f49['gate'] == recon['canonical_gate'] == 'STOP_INSUFFICIENT_FEASIBILITY'
assert f50['gate']['permit_experiment_1'] is False
outcome_diff = [r for r in diff if 'outcome' in r['discrepant_fields']]
assert len(outcome_diff) == len(traces) == 13
assert {r['event_id'] for r in outcome_diff} == {t['event_id'] for t in traces}
diff_by_id = {r['event_id']:r for r in diff}
for trace in traces:
    record = diff_by_id[trace['event_id']]
    e = next(e for e in events if e['event_id']==trace['event_id'])
    sign = e['direction']
    ref, scale = e['reference_price'], e['scale']
    assert trace['reference_price'] == ref and trace['scale_S'] == scale
    assert math.isclose(trace['favorable_price_barrier'],ref*math.exp(sign*2*scale),rel_tol=1e-12)
    assert math.isclose(trace['adverse_price_barrier'],ref*math.exp(-sign*scale),rel_tol=1e-12)
    assert trace['first_touch'] == trace['all_touch_hours'][0]
    previous = -1
    for touch in trace['all_touch_hours']:
        start, end = stamp(touch['open_utc']), stamp(touch['end_utc'])
        assert start > previous and start >= e['data_cutoff'] + HOUR and end <= e['data_cutoff'] + 7*DAY
        previous = start
        assert end == start + HOUR
        assert touch['low'] <= touch['open'] <= touch['high'] and touch['low'] <= touch['close'] <= touch['high']
        good = sign*math.log((touch['high'] if sign==1 else touch['low'])/ref)
        bad = sign*math.log((touch['low'] if sign==1 else touch['high'])/ref)
        assert math.isclose(good,touch['favorable_log_excursion'],rel_tol=1e-12,abs_tol=1e-12)
        assert math.isclose(bad,touch['adverse_log_excursion'],rel_tol=1e-12,abs_tol=1e-12)
        assert touch['hits_favorable'] == (good >= 2*scale)
        assert touch['hits_adverse'] == (bad <= -scale)
    first=trace['first_touch']
    expected='UNKNOWN' if first['hits_favorable'] and first['hits_adverse'] else 'FAILS' if first['hits_adverse'] else 'CONTINUES_'+trace['direction']
    assert record['canonical']['outcome'] == trace['canonical_outcome'] == expected
    assert record['canonical']['barrier_time'] == stamp(first['end_utc'])
geometry={}
boundary_contacts={}
for days in (7,14):
    canonical_groups,_ = components(events, days, LAG)
    cutoff_groups,contacts = components(events, days, 0)
    assert canonical_groups == interval_groups([CandidateEvent(**e) for e in events],days*DAY)
    assert len(canonical_groups) == recon[f'overlap_components_{days}d'] == census[f'overlap_components_{days}d']
    assert len(cutoff_groups) == recon[f'muse_closed_cutoff_components_{days}d']
    geometry[str(days)] = {'canonical_decision_start_components':len(canonical_groups),'cutoff_start_components':len(cutoff_groups)}
    boundary_contacts[str(days)] = contacts
assert geometry == {'7':{'canonical_decision_start_components':128,'cutoff_start_components':117},'14':{'canonical_decision_start_components':47,'cutoff_start_components':45}}
tax = recon['source_taxonomy']
quarantine = tax['quarantine_detail']
assert len(quarantine)==len(f50['quarantine_detail'])==9
assert len({q['open_time'] for q in quarantine})==9
by_open={q['open_time']:q for q in quarantine}
source_rejected=[(f['file'],q) for f in source['files'] for q in f['rejected_rows']]
assert len(source_rejected)==9
for archive,q in source_rejected:
    detail=by_open[q['open_time']]
    assert detail['archive']==archive and detail['close_time_ms']==q['vendor_close_time']
    assert detail['raw_row_sha256']==q['raw_row_sha256']
    assert all(math.isfinite(detail[k]) and detail[k] > 0 for k in ('open','high','low','close'))
    assert detail['low'] <= detail['open'] <= detail['high'] and detail['low'] <= detail['close'] <= detail['high']
    assert math.isfinite(detail['volume']) and detail['volume'] >= 0
for q in f50['quarantine_detail']:
    fields=next(csv.reader(io.StringIO(q['raw'])))
    detail=by_open[int(fields[0])]
    assert digest(fields)==detail['raw_row_sha256']
    assert float(fields[1])==detail['open'] and float(fields[2])==detail['high']
    assert float(fields[3])==detail['low'] and float(fields[4])==detail['close'] and float(fields[5])==detail['volume']
    assert int(fields[6])==detail['close_time_ms']
    assert detail['vendor_close_delta_from_ideal_ms']==int(fields[6])-(int(fields[0])+HOUR-1)
missing=set(tax['missing_vendor_hour_opens'])
excluded=set(by_open)
assert len(missing)==59 and not missing & excluded
unusable=missing | excluded
gaps={t for gap in source['gap_intervals'] for t in range(gap['start'],gap['end'],HOUR)}
assert unusable==gaps and len(unusable)==source['missing_hours']==68
incomplete={t//FOUR_HOURS*FOUR_HOURS+FOUR_HOURS for t in unusable}
assert incomplete==set(tax['incomplete_4h_cutoffs']) and len(incomplete)==35
first=int(datetime(2019,1,1,tzinfo=UTC).timestamp()*1000)
last=int(datetime(2026,1,1,tzinfo=UTC).timestamp()*1000)
cutoffs=list(range(first+FOUR_HOURS,last+1,FOUR_HOURS))
good={t for t in cutoffs if t not in incomplete}
eligible=[t for i,t in enumerate(cutoffs) if i>=180 and all(k in good for k in cutoffs[i-180:i+1])]
assert len(cutoffs)==15342 and len(good)==15307 and len(eligible)==11943
assert len(cutoffs)-180-len(eligible)==3219 and len(good)-180-len(eligible)==3184
assert sum(f['rows'] for f in source['files'])==61300
assert tax['received_vendor_rows']==61300+9==61309
assert tax['expected_hourly_slots']==61309+59==61368
source_copy=dict(source); expected_source=source_copy.pop('manifest_sha256')
assert digest(source_copy)==expected_source
assert len(source['files'])==len(recon['archives'])==84
assert {f['file'] for f in source['files']} == {f'BTCUSDT-1h-{year}-{month:02d}.zip' for year in range(2019,2026) for month in range(1,13)}
assert {f['file']:f['sha256'] for f in source['files']}=={f['file']:f['sha256'] for f in recon['archives']}
assert all(a['sha256']==a['muse_acquired_copy_sha256'] for a in recon['archives'])
legs=read('reconciliation/LEG_DIFF.json')
assert len(legs['canonical_state']['completed_leg_geometry'])==legs['canonical_state']['completed_legs']==156
assert len(legs['canonical_state']['gap_censored_legs'])==14
assert len(legs['canonical_large_completed'])==65
assert Counter(l['direction'] for l in legs['canonical_large_completed'])==Counter({1:33,-1:32})
assert legs['canonical_large_completed']==read('results/EPISODES_DIAGNOSTIC.json')
tier_summary={}
for key in ('perp_1h','funding','metrics','premium_1h'):
    s=tier['sources'][key]
    assert s['present_zip_count']==s['expected_zip_count'] and s['missing_zip_keys']==[] and s['missing_checksum_keys']==[]
    assert s['historical_pit'] is False and s['actual_historical_receipts'] is None
    tier_summary[key]={'expected_files':s['expected_zip_count'],'content_verified_files_reported':len(s['verified_files']),'historical_pit':s['historical_pit']}
assert sum(f['row_count_including_header']-(1 if f['first_row'][0]=='open_time' else 0) for f in tier['sources']['perp_1h']['verified_files'])==52608
assert sum(f['row_count_including_header']-1 for f in tier['sources']['funding']['verified_files'])==6576
fund=tier['sources']['funding']['timestamp_audit']
assert sum(fund['event_time_offset_from_nominal_ms_counts'].values())==6576
assert 6576-fund['event_time_offset_from_nominal_ms_counts']['0']==2882
result={
    'core_import_path':reviewed_core.__file__,
    'python_version':sys.version,
    'label_fingerprint':label_fingerprint,
    'candidate_count':len(rows),'globally_spaced_count':len(spaced),
    'primary_counts':primary_counts,
    'original_discrepancy_counts':dict(original_counts),
    'orientation_only_remaining_counts':dict(repaired_counts),
    'orientation_plus_zero_floor_remaining_counts':{},
    'maximum_geometry_absolute_error':max_error,
    'trace_outcome_differences_verified':len(traces),
    'overlap_geometry':geometry,'cutoff_boundary_contacts':boundary_contacts,
    'source_taxonomy_derived':{'quarantined':9,'missing_vendor_hours':59,'unusable':68,'incomplete_four_hour_groups':35,'eligible_decisions':len(eligible),'unknown_gap_including_missing_cutoffs':3219,'unknown_gap_existing_four_hour':3184},
    'archives_manifest_consistency_count':84,
    'canonical_completed_legs':156,'canonical_large_legs':65,'gap_censored_legs':14,
    'tier_b_internal_manifest_checks':tier_summary,
    'raw_source_authenticity_independently_verified':False,
    'historical_publication_authentication_verified':False,
    'new_real_mom002_outcomes_accessed':False,'scoring_authorized':False,
}
(ROOT/'independent_checks_result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
