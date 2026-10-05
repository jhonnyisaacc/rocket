"""Read-only source-cache byte/inventory check. Never opens ZIP members or acquires data."""
import hashlib
import json
import pathlib
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

PACKET = pathlib.Path('/private/tmp/rocket-foundation-51-independent-2br1p126')
BASE = pathlib.Path('/Users/jhonny/.codex/worktrees/9f31/rocket/.rocket/momentum')
TIER_ROOT = BASE / 'tier-b-audit'
SPOT_ROOT = BASE / 'raw'
OUT = pathlib.Path('/private/tmp/rocket-independent-51-source-cache-check-result.json')
TIER = json.loads((PACKET/'docs/research/momentum/TIER_B_SOURCE_MANIFEST.json').read_text())
SPOT = json.loads((PACKET/'docs/research/momentum/SOURCE_MANIFEST.json').read_text())
ledger = []

def stream_hash(path):
    sha = hashlib.sha256()
    count = 0
    with path.open('rb') as handle:
        while block := handle.read(1024*1024):
            count += len(block)
            sha.update(block)
    return sha.hexdigest(), count

def record(path, root, kind, expected_hash=None, expected_bytes=None, **extra):
    assert path.resolve().is_relative_to(root.resolve()), str(path)
    assert path.is_file(), str(path)
    actual_hash, count = stream_hash(path)
    if expected_hash is not None:
        assert actual_hash == expected_hash, ('hash mismatch', str(path))
    if expected_bytes is not None:
        assert count == expected_bytes, ('size mismatch', str(path))
    row={'path':str(path),'resolved_path':str(path.resolve()),'kind':kind,'bytes':count,'sha256':actual_hash,'expected_sha256':expected_hash,'hash_matches_expected':actual_hash==expected_hash if expected_hash else None}
    row.update(extra)
    ledger.append(row)
    return row

full_path = TIER_ROOT/'FULL_CATALOG_MANIFEST.json'
record(full_path,TIER_ROOT,'full_catalog_manifest',TIER['full_catalog_manifest_sha256'])
full = json.loads(full_path.read_bytes())
assert full['audit'] == TIER['audit'] and full['started_at'] == TIER['started_at'] and full['completed_at'] == TIER['completed_at']
assert set(full['sources']) == set(TIER['sources'])
catalog_entries = {}
catalog_checks = {}
known_cache_files = {full_path.name}

def local_name(element):
    return element.tag.rsplit('}',1)[-1]

def children_text(element):
    return {local_name(child):(child.text or '') for child in element}

for source_name, declared in TIER['sources'].items():
    original = full['sources'][source_name]
    assert original['prefix'] == declared['prefix']
    assert original['catalog_pages'] == declared['catalog_pages']
    assert original['categories'] == declared['categories']
    all_entries, categories = [], []
    next_marker = ''
    for index,page in enumerate(declared['catalog_pages']):
        path=TIER_ROOT/(page['sha256']+'.xml')
        known_cache_files.add(path.name)
        record(path,TIER_ROOT,'catalog_xml',page['sha256'],page['bytes'],source=source_name,declared_url=page['url'])
        tree=ET.fromstring(path.read_bytes())
        scalar={local_name(c):(c.text or '') for c in tree if local_name(c) not in ('Contents','CommonPrefixes')}
        query=parse_qs(urlparse(page['url']).query,keep_blank_values=True)
        assert scalar['Prefix'] == declared['prefix'] == query['prefix'][0]
        assert scalar['Marker'] == next_marker == query.get('marker',[''])[0]
        entries=[children_text(c) for c in tree if local_name(c)=='Contents']
        selected=[{k:entry[k] for k in ('ETag','Key','LastModified','Size')} for entry in entries]
        prefixes=[children_text(c)['Prefix'] for c in tree if local_name(c)=='CommonPrefixes']
        all_entries.extend(selected)
        categories.extend(prefixes)
        if index+1 < len(declared['catalog_pages']):
            assert scalar['IsTruncated'] == 'true' and selected
            next_marker=scalar.get('NextMarker') or selected[-1]['Key']
        else:
            assert scalar['IsTruncated'] == 'false'
    assert all_entries == original['entries']
    assert categories == original['categories']
    assert len({e['Key'] for e in all_entries}) == len(all_entries)
    catalog_entries[source_name] = {e['Key']:e for e in all_entries}
    zip_entries = [e for e in all_entries if e['Key'].endswith('.zip')]
    side_entries = [e for e in all_entries if e['Key'].endswith('.zip.CHECKSUM')]
    summary = declared['catalog_summary']
    assert summary['object_count'] == len(all_entries)
    assert summary['zip_count'] == len(zip_entries) and summary['checksum_count'] == len(side_entries)
    assert summary['first_zip_key'] == (zip_entries[0]['Key'] if zip_entries else None)
    assert summary['last_zip_key'] == (zip_entries[-1]['Key'] if zip_entries else None)
    if all_entries:
        assert summary['last_modified_min'] == min(e['LastModified'] for e in all_entries)
        assert summary['last_modified_max'] == max(e['LastModified'] for e in all_entries)
    catalog_checks[source_name]={'xml_pages':len(declared['catalog_pages']),'catalog_entries':len(all_entries),'catalog_zip_names':len(zip_entries),'catalog_checksum_names':len(side_entries),'complete_pagination_verified':True,'full_manifest_entries_match_xml':True,'categories':categories}
    if 'expected_zip_count' in declared:
        if source_name=='metrics':
            start,last=(date.fromisoformat(s) for s in declared['requested_range'])
            requested=[declared['prefix']+f'BTCUSDT-metrics-{(start+timedelta(days=i)).isoformat()}.zip' for i in range((last-start).days+1)]
        else:
            months=[f'{year}-{month:02d}' for year in range(2020,2026) for month in range(1,13)]
            requested=[declared['prefix']+(f'BTCUSDT-fundingRate-{month}.zip' if source_name=='funding' else f'BTCUSDT-1h-{month}.zip') for month in months]
        missing_zip=[k for k in requested if k not in catalog_entries[source_name]]
        missing_sidecar=[k+'.CHECKSUM' for k in requested if k+'.CHECKSUM' not in catalog_entries[source_name]]
        assert len(requested)==declared['expected_zip_count'] == original['expected_zip_count']
        assert missing_zip == declared['missing_zip_keys'] == original['missing_zip_keys'] == []
        assert missing_sidecar == declared['missing_checksum_keys'] == original['missing_checksum_keys'] == []
        assert declared['present_zip_count']==original['present_zip_count']==len(requested)
        catalog_checks[source_name].update({'requested_zip_names':len(requested),'requested_checksum_names':len(requested),'missing_requested_zip_names':missing_zip,'missing_requested_sidecar_names':missing_sidecar})

def verify_sidecar(path, root, zipped_hash, zip_basename, source, catalog_size=None):
    row=record(path,root,'checksum_sidecar',expected_bytes=catalog_size,source=source)
    fields=path.read_text().split()
    assert len(fields)==2 and fields[0]==zipped_hash and fields[1]==zip_basename, str(path)
    row.update({'declared_zip_sha256':fields[0],'declared_zip_filename':fields[1],'sidecar_digest_matches_zip_and_manifest':True})

tier_zip_counts = {}
verified_file_metadata_differences = {}
for source_name in ('perp_1h','funding','metrics','premium_1h'):
    declared=TIER['sources'][source_name]
    verified=declared['verified_files']
    archived_verified=full['sources'][source_name]['verified_files']
    assert len(verified)==len(archived_verified)
    differences=[]
    for current,archived in zip(verified,archived_verified):
        for key in ('url','checksum_url','sha256','bytes','member'):
            assert current[key]==archived[key]
        changed=[key for key in set(current)|set(archived) if current.get(key)!=archived.get(key)]
        if changed:
            assert source_name=='metrics' and changed==['sample_timestamp_audit']
            differences.append({'url':current['url'],'changed_metadata_keys':changed,'used_for_byte_or_inventory_acceptance':False})
    if differences:
        verified_file_metadata_differences[source_name]=differences
    tier_zip_counts[source_name]=len(verified)
    for item in verified:
        url=urlparse(item['url'])
        assert url.hostname=='data.binance.vision'
        full_key=url.path.removeprefix('/')
        assert full_key in catalog_entries[source_name]
        cache_name=full_key.replace('/','__')
        path=TIER_ROOT/cache_name
        side=TIER_ROOT/(cache_name+'.CHECKSUM')
        known_cache_files.update((path.name,side.name))
        entry=catalog_entries[source_name][full_key]
        assert int(entry['Size'])==item['bytes']
        row=record(path,TIER_ROOT,'tier_b_vendor_zip',item['sha256'],item['bytes'],source=source_name,declared_url=item['url'],catalog_key=full_key)
        assert item['checksum_url']==item['url']+'.CHECKSUM'
        side_entry=catalog_entries[source_name][full_key+'.CHECKSUM']
        verify_sidecar(side,TIER_ROOT,row['sha256'],pathlib.PurePosixPath(full_key).name,source_name,int(side_entry['Size']))

actual_cache_files={p.name for p in TIER_ROOT.iterdir() if p.is_file()}
assert actual_cache_files==known_cache_files
assert len(actual_cache_files)==310
assert Counter(tier_zip_counts)==Counter({'perp_1h':72,'funding':72,'metrics':3,'premium_1h':2})
spot_names={f['file'] for f in SPOT['files']}
assert len(SPOT['files'])==len(spot_names)==84
assert spot_names=={f'BTCUSDT-1h-{year}-{month:02d}.zip' for year in range(2019,2026) for month in range(1,13)}
for item in SPOT['files']:
    path=SPOT_ROOT/item['file']
    row=record(path,SPOT_ROOT,'spot_vendor_zip',item['sha256'],source='spot',declared_url=item['url'])
    verify_sidecar(SPOT_ROOT/(item['file']+'.CHECKSUM'),SPOT_ROOT,row['sha256'],item['file'],'spot')

kind_counts=dict(Counter(r['kind'] for r in ledger))
result={
    'decision':'OFFLINE_CACHE_BYTE_INTEGRITY_AND_CATALOG_INVENTORY_VERIFIED',
    'tier_cache_path':str(TIER_ROOT),'spot_cache_path':str(SPOT_ROOT),
    'tier_source_manifest_sha256':stream_hash(PACKET/'docs/research/momentum/TIER_B_SOURCE_MANIFEST.json')[0],
    'spot_source_manifest_sha256':stream_hash(PACKET/'docs/research/momentum/SOURCE_MANIFEST.json')[0],
    'full_catalog_manifest_sha256':TIER['full_catalog_manifest_sha256'],
    'tier_zip_counts':tier_zip_counts,'spot_zip_count':84,
    'kind_counts':kind_counts,'inspected_file_count':len(ledger),'total_cached_bytes_hashed':sum(r['bytes'] for r in ledger),
    'catalog_checks':catalog_checks,
    'verified_file_metadata_differences_between_full_and_reviewed_manifest':verified_file_metadata_differences,
    'catalog_total_object_entries':sum(v['catalog_entries'] for v in catalog_checks.values()),
    'tier_requested_zip_names_verified_in_catalog':sum(v.get('requested_zip_names',0) for v in catalog_checks.values()),
    'tier_requested_sidecar_names_verified_in_catalog':sum(v.get('requested_checksum_names',0) for v in catalog_checks.values()),
    'sidecar_text_parsed':True,'catalog_metadata_parsed':True,
    'zip_member_contents_decoded':False,'raw_arrays_inspected':False,'features_computed':False,'targets_computed':False,'network_used':False,
    'authenticated_vendor_origin_proven':False,'original_historical_vintages_proven':False,'historical_receipts_or_publication_proven':False,'raw_tape_computational_replication_performed':False,'full_feature_window_completeness_proven':False,
    'new_real_mom002_outcomes_accessed':False,'scoring_authorized':False,
    'inspected_cache_files':ledger,
}
with OUT.open('x') as handle:
    json.dump(result,handle,indent=2);handle.write('\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('inspected_cache_files','catalog_checks')},indent=2))
