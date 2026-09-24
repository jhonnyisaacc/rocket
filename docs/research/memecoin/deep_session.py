"""Frozen three-hour research session. No automatic extension or execution."""
import datetime as dt
import hashlib
import json
from pathlib import Path
from pilot_capture import BASE,OUT,stamp

ROOT=BASE/'data'/'session-2026-09-21-deep-dive'
MANIFEST=ROOT/'manifest.json'
PUMP='6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
SEEDS={
 'unipcs':'2heJbC32Tpfcb3nbUb5ER61K11FGZVfVGtVnDm6LDogF',
 'GMannnnn':'FPLXEqws2rKy4k8B2tARTGV632fYCnPqxEktVMKfJ2H9',
 'anonymous_calibration':'789sBYAGntSyAPoS4ZH3zo3SUFuv1jeAjPeaq7muVany'}

def epoch(s):return int(dt.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
def save_new(path,value):
    with Path(path).open('x') as f:f.write(json.dumps(value,indent=2)+'\n')

def initialize():
    ROOT.mkdir(parents=True,exist_ok=True)
    if MANIFEST.exists():raise ValueError('Session already initialized')
    hashes={str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(BASE.rglob('*')) if p.is_file() and ROOT not in p.parents and '__pycache__' not in p.parts}
    save_new(ROOT/'baseline_hashes.json',hashes)
    save_new(MANIFEST,{
      'session':'2026-09-21-deep-dive','root':str(ROOT),'started_at':'2026-09-21T19:42:59Z',
      'deadline_at':'2026-09-21T22:42:59Z','acquisition_deadline_at':'2026-09-21T22:12:59Z',
      'helius_credit_cap':10000,'credit_buckets':{'public':1000,'wallets':1200,'cohort':2000,'development':2800,'holdout':2000,'contingency':1000},
      'request_policy':{'max_history_records':1000,'max_history_interval_seconds':259200},
      'cache_roots':[str(OUT),str(BASE/'data'/'session-2026-09-21-continuation')],
      'edge':'NO_EDGE_VALIDATED','automation':'PAUSED','execution_enabled':False,'baseline_tests_passed':75,
      'seed_wallets':SEEDS,'seed_history_interval':{'gte':epoch('2026-09-10T00:00:00Z'),'lt':epoch('2026-09-13T00:00:00Z')},
      'seed_max_pages_per_wallet':4,'seed_page_size':1000,
      'cohort':{split:{'gte':epoch(date+'T12:00:00Z'),'lt':epoch(date+'T12:10:00Z')}
                for split,date in [('development','2026-09-14'),('holdout','2026-09-17')]},
      'cohort_max_pages_per_partition':10,'cohort_page_size':1000,'cohort_target_mints':12,
      'cohort_selection':'First distinct verified native-SOL Pump creations in slot/transaction/instruction order. Partial prefix if capped; no replacement or date widening.',
      'excluded_mints':['435CfmvrJ4QtkVv4cZ1TbUa7rzrKKjvQJLMnvhTCpump','EcPhZph4VXgHW279x5bYX2VjvWBHW5TTQingCAtEpump'],
      'public_profile_rule':'First four distinct eligible default-feed profiles excluding unipcs, GMannnnn, Rochaboyyyy, therear66; no replacement for unsupported chain, missing mapping or poor performance.',
      'development_history_seconds':900,'development_max_pages_per_mint':2,'development_page_size':1000,
      'holdout_max_pages_per_mint':1,'holdout_page_size':1000,
      'shortlist':{'max_wallets':8,'candidate_buyers_per_mint':5,'max_entry_age_seconds':300,
                   'sort':['distinct_development_mints_desc','median_entry_age_asc','address_asc'],
                   'exclude':['creator','unsigned_economic_owner','infrastructure_or_unresolved_router']},
      'hypotheses':{'H1':'First shortlisted genuine buyer in first 300 seconds',
                    'H2':'Two distinct shortlisted genuine buyers within trailing 60 seconds',
                    'H3':'At least 10 percent drawdown from preceding 60-second reserve-price high, followed within 60 seconds by two shortlisted buyers with positive combined net acquisition'},
      'hypothesis_observation_seconds':300,
      'controls':{'momentum':'First 10 percent reserve-price rise from state at or before t-60 during first 300 seconds; require full 60-second history',
                  'ordinary_buyer':'Nearest strictly preceding non-shortlisted non-creator buy in same token-age minute; missing is unmatched'},
      'sizes_lamports':[10000000,100000000,500000000],'primary_size_lamports':100000000,
      'delays_seconds':[5,15,30],'primary_delay_seconds':15,'holding_seconds':[300,900],
      'slippage_bps':200,'max_entries_per_token_hypothesis_scenario':1,
      'relationship_flags':'Only observed creator identity or direct pre-trigger funding; common payer/router/exchange insufficient. Unknown relationship coverage is disclosed.',
      'holdout_policy':'No holdout API capture before immutable shortlist + implementation lock. Contaminated data lose untouched status.',
      'historical_available_at':None,'simulation_kind':'historical-state approximation, not measured bot latency or historically available identities',
      'compatibility_gate_minutes':30,'primary_papers_max':3,'actual_provider_billing':None,
      'separate_frozen_september13_experiment':'preserved, not executed or modified by this session'})
    print(str(MANIFEST))

if __name__=='__main__':initialize()
