"""Local reproducible entry audit; never imports or modifies production code."""
import ast
import hashlib
import json
import math
import random
from pathlib import Path
from datetime import datetime, timezone
import httpx

ROOT = Path(__file__).resolve().parent
STEP = 14400000
COINS = ['BTC', 'ETH', 'SOL', 'XRP', 'HYPE', 'ZEC']
END = int(datetime(2026,9,16,12,tzinfo=timezone.utc).timestamp()*1000)
START = END - 180 * 86400000

def save(path, obj):
    path.write_text(json.dumps(obj, indent=2))

def acquire():
    path = ROOT / 'dataset.json'
    if path.exists():
        return json.loads(path.read_text())
    data = {'start': START, 'end': END, 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'assets': {}}
    with httpx.Client(timeout=45) as client:
        def request(body):
            response = client.post('https://api.hyperliquid.xyz/info', json=body)
            response.raise_for_status()
            return response.json()
        for coin in COINS:
            raw = request({'type':'candleSnapshot','req':{'coin':coin,'interval':'4h','startTime':START,'endTime':END}})
            bars = sorted([{'t':int(b['t']), **{k:float(b[k]) for k in ['o','h','l','c']}} for b in raw if START <= int(b['t']) and int(b['t'])+STEP <= END], key=lambda b:b['t'])
            assert len(bars) == 1080, (coin, len(bars))
            assert all(b['l'] <= min(b['o'],b['c']) <= max(b['o'],b['c']) <= b['h'] for b in bars)
            assert all(bars[i]['t']-bars[i-1]['t']==STEP for i in range(1,len(bars)))
            funding, cursor, error = [], START, None
            try:
                while cursor < END:
                    page = request({'type':'fundingHistory','coin':coin,'startTime':cursor,'endTime':END})
                    if not page: break
                    funding.extend(page)
                    cursor = max(int(x['time']) for x in page)+1
                funding = sorted({int(x['time']):x for x in funding}.values(),key=lambda x:int(x['time']))
            except Exception as exc:
                error = type(exc).__name__
            data['assets'][coin] = {'bars':bars,'funding':funding,'funding_error':error}
            print(coin, len(bars), 'bars', len(funding), 'funding records', flush=True)
    save(path,data)
    return data

def load_rule():
    snapshot = ROOT / 'rule_snapshot.py'
    if not snapshot.exists():
        source = Path('/Users/jhonny/rocket/rocket/workflows/crypto.py').read_text()
        tree = ast.parse(source)
        names = {'_ohlc','structure_state','setup_from_candles'}
        text = 'from __future__ import annotations\nimport math\nSTRUCTURE_BARS=6\nMIN_SETUP_BARS=24\nNO_CHASE_PCT=0.02\n'
        text += '\n\n'.join(ast.get_source_segment(source,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names)
        snapshot.write_text(text)
    scope = {}
    exec(snapshot.read_text(),scope)
    return scope['setup_from_candles']

def simulate(bars,i,s,mode,bound):
    step=bars[1]['t']-bars[0]['t']
    wait=8*86400000//step
    direction = 1 if s['direction']=='long' else -1
    stop = s['invalidation']
    limit = s['entry_zone'][1 if direction==1 else 0]
    row = {'signal_index':i,'signal_time':bars[i]['t']+step,'direction':direction,'stop':stop,'zone':s['entry_zone'],'mode':mode,'bound':bound}
    for j in range(i+1, min(i+(1 if mode=='immediate' else wait)+1,len(bars))):
        b=bars[j]
        if direction*(b['o']-stop)<=0:
            return {**row,'status':'invalidated_before_entry','end_index':j}
        touched = mode=='immediate' or (b['l']<=limit if direction==1 else b['h']>=limit)
        if not touched: continue
        entry = b['o'] if mode=='immediate' or direction*(b['o']-limit)<=0 else limit
        risk = direction*(entry-stop)
        target=entry+direction*risk
        # Touch-time uncertainty is at most one execution bar.
        final = j+48*3600000//step-1
        for k in range(j, min(final+1,len(bars))):
            bar=bars[k]
            sh=bar['l']<=stop if direction==1 else bar['h']>=stop
            th=bar['h']>=target if direction==1 else bar['l']<=target
            intrabar_entry = k==j and entry!=b['o']
            ambiguous = sh and th or (intrabar_entry and th)
            price=None
            reason=None
            if k>j and direction*(bar['o']-stop)<=0: price,reason=bar['o'],'gap_stop'
            elif k>j and direction*(bar['o']-target)>=0: price,reason=target,'target'
            elif ambiguous:
                if bound=='optimistic': price,reason=target,'ambiguous_target'
                elif sh: price,reason=stop,'ambiguous_stop'
                # If only target touched on entry bar, pessimistic assumes before entry.
            elif sh: price,reason=stop,'stop'
            elif th: price,reason=target,'target'
            if price is None and k==final: price,reason=bar['c'],'timeout'
            if price is not None:
                return {**row,'status':reason,'entry':entry,'target':target,'risk':risk,'entry_index':j,'end_index':k,'entry_time':b['t'],'exit_time':bar['t']+step,'gross_r':direction*(price-entry)/risk,'exit':price}
        return {**row,'status':'censored','end_index':len(bars)-1}
    return {**row,'status':'expired','end_index':min(i+wait,len(bars)-1)}

def main():
    data=acquire(); rule=load_rule(); ledger=[]; rawcounts={}; legacy=[]
    fine=json.loads((ROOT/'hourly.json').read_text()) if (ROOT/'hourly.json').exists() else None
    for coin,a in data['assets'].items():
        bars=a['bars']; signals={}
        for i in range(24,len(bars)-60):
            s=rule([{'high':b['h'],'low':b['l'],'close':b['c']} for b in bars[:i+1]])
            if s.get('valid'): signals[i]=s
        rawcounts[coin]={'signals':len(signals),'in_zone':sum(s['entry_zone'][0]<=bars[i]['c']<=s['entry_zone'][1] for i,s in signals.items())}
        # Reproduce old overlapping diagnostic on this frozen sample.
        for i,s in signals.items():
            d=1 if s['direction']=='long' else -1; entry=s['entry_zone'][1 if d==1 else 0]; stop=s['invalidation']; target=entry+d*abs(entry-stop)
            outcome='untriggered'
            for j in range(i+1,i+49):
                b=bars[j]
                if b['l']<=s['entry_zone'][1] and b['h']>=s['entry_zone'][0]:
                    outcome='unresolved'
                    if (b['l']<=stop if d==1 else b['h']>=stop): outcome='ambiguous'; break
                    for k in range(j+1,j+13):
                        b=bars[k]; sh=b['l']<=stop if d==1 else b['h']>=stop; th=b['h']>=target if d==1 else b['l']<=target
                        if sh or th: outcome='ambiguous' if sh and th else 'win' if th else 'loss'; break
                    break
            legacy.append(outcome)
        for mode in ['immediate','retest']:
            for bound in ['pessimistic','optimistic']:
                busy=-1
                for i,s in signals.items():
                    if i<busy:
                        ledger.append({'coin':coin,'mode':mode,'bound':bound,'signal_index':i,'status':'suppressed_overlap'})
                        continue
                    execution=fine['assets'][coin] if fine else bars
                    row=simulate(execution,4*i+3 if fine else i,s,mode,bound)
                    if fine:
                        row['end_index']//=4
                        if 'entry_index' in row: row['entry_index']//=4
                    row['signal_index']=i
                    busy=row['end_index']
                    row.update(coin=coin,period='early' if i<660 else 'purged' if i<720 else 'later')
                    if 'entry' in row:
                        rates=[x for x in a['funding'] if row['entry_time']<int(x['time'])<=row['exit_time']]
                        complete=len(rates)==(row['exit_time']-row['entry_time'])//3600000
                        row['funding_complete']=complete
                        row['funding_r']=row['direction']*sum(float(x['fundingRate']) for x in rates)*row['entry']/row['risk'] if complete else None
                        for bps in [10,20,40]:
                            row[f'net_{bps}bps_r']=row['gross_r']-bps/10000*row['entry']/row['risk']-(row['funding_r'] or 0)
                        row['exposure_hours']=(row['exit_time']-row['entry_time'])/3600000
                    ledger.append(row)
    save(ROOT/'ledger.json',ledger)
    groups={}
    for mode in ['immediate','retest']:
        for bound in ['pessimistic','optimistic']:
            filled=[r for r in ledger if r['mode']==mode and r['bound']==bound and 'entry' in r]
            strongest=max(COINS,key=lambda c:sum(r['net_20bps_r'] for r in filled if r['coin']==c))
            for group in ['all','without_HYPE','without_strongest','early','later']+COINS:
                rows=[r for r in filled if group=='all' or group=='without_HYPE' and r['coin']!='HYPE' or group=='without_strongest' and r['coin']!=strongest or group in ['early','later'] and r['period']==group or r['coin']==group]
                if not rows: continue
                vals=[r['net_20bps_r'] for r in rows]; rng=random.Random(42)
                boot=sorted(sum(rng.choices(vals,k=len(vals)))/len(vals) for _ in range(2000))
                equity=peak=dd=0
                for r in sorted(rows,key=lambda r:r['exit_time']):
                    equity+=r['net_20bps_r']; peak=max(peak,equity); dd=max(dd,peak-equity)
                groups[f'{mode}/{bound}/{group}']={'n':len(rows),'net_mean_r':{str(b):sum(r[f'net_{b}bps_r'] for r in rows)/len(rows) for b in [10,20,40]},'naive_bootstrap95_mean_r':[boot[50],boot[1949]],'closed_trade_drawdown_r':dd,'exposure_asset_hours':sum(r['exposure_hours'] for r in rows),'missing_funding_trades':sum(not r['funding_complete'] for r in rows),'timeouts':sum(r['status']=='timeout' for r in rows)}
    summary={'execution_interval':'1h' if fine else '4h','raw_signals':rawcounts,'legacy':{s:legacy.count(s) for s in set(legacy)},'groups':groups,'dataset_sha256':hashlib.sha256((ROOT/'dataset.json').read_bytes()).hexdigest(),'rule_sha256':hashlib.sha256((ROOT/'rule_snapshot.py').read_bytes()).hexdigest()}
    summary['legacy']=dict(sorted(summary['legacy'].items()))
    save(ROOT/'summary.json',summary)
    print(json.dumps({k:v for k,v in groups.items() if k.endswith('/all') or k.endswith('/without_HYPE')},indent=2))

if __name__=='__main__': main()
