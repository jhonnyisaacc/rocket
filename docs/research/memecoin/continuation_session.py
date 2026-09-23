"""Explicitly bounded second session; initialization captures the unchanged baseline."""
import datetime as dt
import hashlib
import json
from pathlib import Path
from pilot_capture import BASE, OUT

ROOT = BASE/'data'/'session-2026-09-21-continuation'
START = '2026-09-21T19:04:45Z'
DEADLINE = '2026-09-21T20:04:45Z'
ACQUISITION_DEADLINE = '2026-09-21T19:54:45Z'
MANIFEST = ROOT/'manifest.json'
UNIPCS = '2heJbC32Tpfcb3nbUb5ER61K11FGZVfVGtVnDm6LDogF'
CATE_KEYS = ['dbae79a172a6189fcd82eaac74bbebc786fc23dad81ff25a40abfd489b45ea8f',
             '9f5ca922e2d6547ad525c4a3ef9f316c6f1f5ffb09307ed9c5b85e951883edc4']

def save_new(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2)+'\n')

def initialize():
    ROOT.mkdir(parents=True, exist_ok=True)
    if MANIFEST.exists():
        return
    # Hash every existing research file (excluding transient bytecode), before
    # any decoder/capture changes. Raw and closed-session artifacts stay immutable.
    hashes={str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(BASE.rglob('*')) if p.is_file() and ROOT not in p.parents
            and '__pycache__' not in p.parts}
    save_new(ROOT/'baseline_hashes.json', hashes)
    save_new(MANIFEST, dict(session='2026-09-21-continuation',started_at=START,
        deadline_at=DEADLINE,acquisition_deadline_at=ACQUISITION_DEADLINE,
        root=str(ROOT),cache_roots=[str(OUT)],helius_credit_cap=1000,
        credit_buckets={'discovery':400,'wallets':200,'gaps':200,'contingency':200},
        baseline_tests={'passed':46,'failed':0},edge='NO_EDGE_VALIDATED',
        execution_enabled=False,automation='PAUSED',
        cate_origin_keys=CATE_KEYS,cate_max_new_pages_per_window=20,
        unipcs_wallet=UNIPCS,unipcs_interval={'gte':1788102082-150,'lt':1788102082+150},
        unipcs_max_pages=20,
        pricing_sources=['https://www.helius.dev/docs/rpc/gettransactionsforaddress',
                         'https://www.helius.dev/docs/billing/credits'],
        pricing_checked_at='2026-09-21T19:05:00Z',
        pricing={'full_history_up_to_100_records':10,'archival_transaction':1,'block_signatures':1},
        actual_provider_billing=None,
        completion_rule='Close within 60 minutes; no automatic extension; preserve partial coverage'))

if __name__=='__main__':
    initialize()
    print(str(MANIFEST))
