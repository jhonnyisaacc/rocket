"""Local capture / verify / replay / report. No production imports or orders."""
import argparse, hashlib, importlib.util, json, math, random, shutil, subprocess, sys
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from engine import H,D,W,MONDAY,frame,aggregate,impulses
from execution import simulate

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'entry_audit'
COINS=['BTC','ETH','SOL','XRP','HYPE','ZEC']

def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n')
def immutable(p,obj):
    if p.exists():assert read(p)==obj,f'Immutable artifact differs: {p}'
    else:save(p,obj)
def utc(t):return datetime.fromtimestamp(t/1000,timezone.utc).isoformat()
def inputs():return read(ROOT/'inputs/dataset.json'),read(ROOT/'inputs/hourly.json')

def capture(probe=False,retry_probe=False):
    if not (ROOT/'capture.json').exists():
        p=ROOT/'inputs';p.mkdir(exist_ok=True)
        names=['dataset.json','hourly.json','run.py','rule_snapshot.py','ledger.json','summary.json','manifest.json']
        sources={}
        for name in names:
            src=OLD/name;dest=p/name;shutil.copyfile(src,dest)
            sources[str(src)]=dict(sha256=sha(src),snapshot=str(dest.relative_to(ROOT)))
        for src in [ROOT.parent/'theory_alignment_v1/DECISION.md',ROOT.parent/'theory_alignment_v1/RECOVERED_RULES.md',
                    ROOT.parent/'btc_september_v1/archive_evidence.json',
                    ROOT.parent/'btc_september_v1/raw_5m.json',
                    Path('/Users/jhonny/nave/docs/technical.yaml'),Path('/Users/jhonny/nave/docs/elcriptopanavideos.md')]:
            dest=p/src.name;shutil.copyfile(src,dest)
            sources[str(src)]=dict(sha256=sha(src),snapshot=str(dest.relative_to(ROOT)))
        data,hourly=inputs()
        save(ROOT/'capture.json',dict(captured_at=now(),sources=sources,
            original_retrieval=data.get('retrieved_at'),hourly_retrieval=hourly.get('retrieved_at'),
            historical_exchange_raw_responses='NOT preserved by original six-asset acquisition; normalized snapshots only',
            extension='Not merged: retain shared frozen six-asset experiment window. Coverage probe stored separately.'))
    probe_path=ROOT/('provider_probe_retry.json' if retry_probe else 'provider_probe.json')
    if probe and not probe_path.exists():
        import httpx
        data,_=inputs();p=ROOT/('raw_probe_retry' if retry_probe else 'raw_probe');p.mkdir(exist_ok=True);results=[]
        requests=[dict(type='meta'),dict(type='candleSnapshot',req=dict(coin='BTC',interval='1h',startTime=data['start'],endTime=data['end']))]
        with httpx.Client(timeout=25) as client:
            for i,body in enumerate(requests):
                record=dict(request=body,retrieved_at=now())
                try:
                    r=client.post('https://api.hyperliquid.xyz/info',json=body)
                    dest=p/f'{i}.json';dest.write_bytes(r.content)
                    record.update(status=r.status_code,sha256=sha(dest),raw=str(dest.relative_to(ROOT)))
                    r.raise_for_status();obj=r.json()
                    if isinstance(obj,list):record.update(count=len(obj),first=min((x['t'] for x in obj),default=None),last=max((x['t'] for x in obj),default=None))
                except Exception as exc:record['error_type']=type(exc).__name__
                results.append(record)
        save(probe_path,dict(results=results,note='Current metadata not historical metadata. Probe is not merged or labeled unseen validation.'))
    print('Capture preserved:',ROOT/'capture.json')

def verify_data():
    data,hourly=inputs();result={}
    for c in COINS:
        bs=hourly['assets'][c];h4=data['assets'][c]['bars']
        assert [b['t'] for b in bs]==list(range(data['start'],data['end'],H)),c
        assert all(b['l']<=min(b['o'],b['c'])<=max(b['o'],b['c'])<=b['h'] for b in bs)
        assert aggregate(bs,4*H,data['end'])==h4,c
        rates=data['assets'][c]['funding'];buckets=[int(r['time'])//H*H for r in rates]
        assert len(buckets)==len(set(buckets)),c
        result[c]=dict(hourly=len(bs),four_hour=len(h4),funding=len(rates),
            funding_missing=len(set(range(data['start'],data['end'],H))-set(buckets)),
            start=utc(bs[0]['t']),end=utc(bs[-1]['t']+H),aggregation_exact=True)
    for src,r in read(ROOT/'capture.json')['sources'].items():
        assert sha(ROOT/r['snapshot'])==r['sha256']
        assert sha(Path(src))==r['sha256'],f'Upstream changed: {src}'
    return result

def verify():
    coverage=verify_data()
    p=subprocess.run([sys.executable,'-m','unittest','-v','test_contract'],cwd=ROOT,capture_output=True,text=True)
    (ROOT/'test_results.txt').write_text(p.stdout+p.stderr)
    assert p.returncode==0,p.stderr
    protected=['CONTRACT.md','engine.py','execution.py','test_contract.py']
    hashes={name:sha(ROOT/name) for name in protected}
    seal=ROOT/'contract_seal.json'
    if seal.exists():assert read(seal)['hashes']==hashes,'Frozen contract changed'
    else:save(seal,dict(sealed_at=now(),hashes=hashes,test_returncode=p.returncode,
        statement='Frozen after fixture verification, before new historical replay outcomes.'))
    save(ROOT/'verification.json',dict(verified_at=now(),coverage=coverage,tests_pass=True,contract_hashes=hashes))
    print('Fixtures and coverage verified; contract sealed.')

def baseline():
    folder=ROOT/'baseline_reproduction';folder.mkdir(exist_ok=True)
    spec=importlib.util.spec_from_file_location('frozen_old_run',ROOT/'inputs/run.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    old.ROOT=folder
    for name in ['dataset.json','hourly.json','rule_snapshot.py']:shutil.copyfile(ROOT/'inputs'/name,folder/name)
    old.main()
    ledger_equal=read(folder/'ledger.json')==read(ROOT/'inputs/ledger.json')
    summary_equal=read(folder/'summary.json')==read(ROOT/'inputs/summary.json')
    assert ledger_equal and summary_equal,'Baseline parity failed'
    save(ROOT/'baseline_parity.json',dict(ledger_exact=ledger_equal,summary_exact=summary_equal,
        rows=len(read(folder/'ledger.json')),known_limitations='Legacy overlap boundary and funding timestamp count issues intentionally reproduced; not corrected economic reference.'))

def compute_frames(hours):
    # Process only completed 4h closes. Feature construction sees prefixes only.
    times=[b['t']+H for b in hours if (b['t']+H)%(4*H)==0]
    return [dict(frame(hours,t),index=i) for i,t in enumerate(times)]

def finer_btc(hours):
    raw=read(ROOT/'inputs/raw_5m.json');raw=raw.get('response',raw) if isinstance(raw,dict) else raw
    groups=defaultdict(list);valid={}
    for b in raw:
        groups[int(b['t'])//H*H].append(dict(t=int(b['t']),_step=H//12,**{k:float(b[k]) for k in ('o','h','l','c')}))
    for b in hours:
        bs=sorted(groups[b['t']],key=lambda x:x['t'])
        if [x['t'] for x in bs]!=list(range(b['t'],b['t']+H,H//12)):continue
        actual=dict(t=b['t'],o=bs[0]['o'],h=max(x['h'] for x in bs),l=min(x['l'] for x in bs),c=bs[-1]['c'])
        if actual==b:valid[b['t']]=bs
    return valid

def replay():
    verify_data()
    assert (ROOT/'contract_seal.json').exists(),'Run verify before replay'
    for name,h in read(ROOT/'contract_seal.json')['hashes'].items():assert sha(ROOT/name)==h
    baseline()
    data,hourly=inputs();decisions=[];ledger=[];counts={}
    for coin in COINS:
        print('Features',coin,flush=True)
        finer=finer_btc(hourly['assets'][coin]) if coin=='BTC' else {}
        cache=ROOT/'frames'/f'{coin}.json'
        if cache.exists():fs=read(cache)
        else:fs=compute_frames(hourly['assets'][coin]);save(cache,fs)
        busy=0;seen=set();local=[]
        for f in fs:
            row=dict(f,coin=coin,status='rejected' if f['blockers'] else 'eligible')
            if f['eligible']:
                key=(f['direction'],f['leg']['origin_t'])
                if f['time']<busy:row['status']='suppressed_active'
                elif key in seen:row['status']='suppressed_reentry'
                else:
                    seen.add(key);row['status']='admitted';hid=f'{coin}:{f["time"]}'
                    # As-of future opposite daily BOS supplies lifecycle events,
                    # never admission evidence. Frozen anchors remain unchanged.
                    ds=aggregate(hourly['assets'][coin],D,data['end']);states=impulses(ds)
                    invalid=[b['t']+D for b,s in zip(ds,states) if s and s['direction']!=f['direction']]
                    paths=[]
                    for mode in ('passive','flip'):
                        for path in ('OLHC','OHLC'):
                            r=simulate(hourly['assets'][coin],f,mode,path,data['assets'][coin]['funding'],invalid,finer)
                            r.update(coin=coin,hypothesis=hid,index=f['index'],hypothesis_record=f)
                            paths.append(r)
                    busy=max(r['end_time'] for r in paths);ledger.extend(paths)
            local.append(row)
        decisions.extend(local)
        counts[coin]=dict(decisions=len(local),statuses=dict(Counter(r['status'] for r in local)),
            blockers=dict(Counter(x for r in local for x in r['blockers'])),
            sole_blocker=dict(Counter(r['blockers'][0] for r in local if len(r['blockers'])==1)))
        print(coin,counts[coin]['statuses'],flush=True)
    immutable(ROOT/'decisions.json',decisions);immutable(ROOT/'ledger.json',ledger)
    immutable(ROOT/'funnel.json',counts)
    save(ROOT/'replay_record.json',dict(completed_at=now(),contract_seal_sha256=sha(ROOT/'contract_seal.json'),
         decisions_sha256=sha(ROOT/'decisions.json'),ledger_sha256=sha(ROOT/'ledger.json')))
    print('Replay complete',len(decisions),'decisions',len(ledger),'policy/path rows')

def bootstrap(rows,key):
    weeks=defaultdict(list)
    for r in rows:weeks[(r['time']-MONDAY)//W].append(r['economics']['net']['20'][key])
    if len(weeks)<2:return None
    rng=random.Random(20260921);values=[]
    for _ in range(2000):
        vals=[v for w in rng.choices(sorted(weeks),k=len(weeks)) for v in weeks[w]]
        values.append(sum(vals)/len(vals))
    values.sort();return [values[49],values[1949]]

def summaries(ledger,data):
    groups={}
    for mode in ('passive','flip'):
      for path in ('OLHC','OHLC'):
        base=[r for r in ledger if r['mode']==mode and r['path']==path]
        good=[r for r in base if r.get('economics',{}).get('net',{}).get('20') is not None]
        for sizing,key in [('R','r_lower'),('notional','notional_lower')]:
          strongest=max(COINS,key=lambda c:sum(r['economics']['net']['20'][key] for r in good if r['coin']==c)) if good else None
          cut1=data['start']+660*4*H;cut2=data['start']+720*4*H
          for group in ['all','without_HYPE','without_strongest','development','later']+COINS:
            def keep(r):
                return group=='all' or group=='without_HYPE' and r['coin']!='HYPE' or group=='without_strongest' and r['coin']!=strongest or group=='development' and r['time']<cut1 and r['end_time']<=cut1 or group=='later' and r['time']>=cut2 or group==r['coin']
            selected=[r for r in base if keep(r)];rs=[r for r in good if keep(r)]
            equity=peak=dd=0
            for r in sorted(rs,key=lambda r:(r['end_time'],r['coin'])):
                equity+=r['economics']['net']['20'][key];peak=max(peak,equity);dd=max(dd,peak-equity)
            groups[f'{mode}/{path}/{sizing}/{group}']=dict(hypotheses=len(selected),fills=sum('entry' in r for r in selected),
                completed_net_observations=len(rs),statuses=dict(Counter(r['status'] for r in selected)),
                net_mean={str(b):sum(r['economics']['net'][str(b)][key] for r in rs)/len(rs) if rs else None for b in (10,20,40)},
                closed_trade_drawdown20=dd if rs else None,exposure_asset_hours=sum(r.get('economics',{}).get('exposure_hours',0) for r in selected),
                occupied_admission_weeks=len({(r['time']-MONDAY)//W for r in rs}),
                descriptive_week_bootstrap95=bootstrap(rs,key),excluded_strongest=strongest,
                scheduled_observable_fills=sum(r.get('scheduled_observable',False) for r in selected))
    return groups

def report():
    from presentation import publish
    data,_=inputs();ledger=read(ROOT/'ledger.json');groups=summaries(ledger,data)
    save(ROOT/'summary.json',groups);publish(ROOT)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['capture','verify','replay','report']);p.add_argument('--probe',action='store_true');p.add_argument('--retry-probe',action='store_true')
    a=p.parse_args()
    if a.stage=='capture':capture(a.probe,a.retry_probe)
    else:globals()[a.stage]()

if __name__=='__main__':main()
