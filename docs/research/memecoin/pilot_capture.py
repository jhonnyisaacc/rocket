"""Read-only, cache-first capture with a durable, conservative credit reservation.

No secret in cache keys, logs or errors. An ambiguous failed dispatch remains
charged against the local budget; it is never automatically retried.
"""
import datetime as dt
import fcntl
import hashlib
import json
from pathlib import Path
import tomllib
import urllib.request

BASE=Path(__file__).resolve().parent
OUT=BASE/'data'/'session-2026-09-21'
CAPS={'state':400,'wallets':200,'gaps':200,'contingency':200}

def stable(value):return json.dumps(value,sort_keys=True,separators=(',',':'))
def digest(value):return hashlib.sha256(stable(value).encode()).hexdigest()
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()

def cost(method,params,policy=None):
    policy=policy or {}
    if method=='getTransactionsForAddress':
        opts=params[1]
        limit=opts.get('limit',0)
        if opts.get('transactionDetails')!='full' or not isinstance(limit,int) or not 1<=limit<=policy.get('max_history_records',100):
            raise ValueError('Only bounded full history requests supported')
        bounds=opts.get('filters',{}).get('blockTime',{})
        maximum=policy.get('max_history_interval_seconds',300)
        if not isinstance(bounds.get('gte'),int) or not isinstance(bounds.get('lt'),int) or not 0<bounds['lt']-bounds['gte']<=maximum:
            raise ValueError('History requests require an explicit bounded interval')
        return 10*((limit+99)//100)
    if method=='getBlock' and params[1].get('transactionDetails')=='signatures':return 1
    if method=='getTransaction':return 1
    raise ValueError('Method not authorized by research capture allowlist')

def network(body):
    config=tomllib.loads(Path('/Users/jhonny/.codex/config.toml').read_text())
    key=config['mcp_servers']['helius']['env']['HELIUS_API_KEY']
    req=urllib.request.Request('https://mainnet.helius-rpc.com/?api-key='+key,
                               data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)

class Capture:
    def __init__(self,root=OUT,transport=network,deadline=None,config=None,cache_roots=(),retry_authorizations=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.transport=transport
        if config is None and self.root.resolve()==OUT.resolve():
            config=json.loads((BASE/'session_20260921_manifest.json').read_text())
        self.config=config
        self.retry_authorizations=retry_authorizations or {}
        self.cache_roots=tuple(Path(p) for p in cache_roots)
        self.request_policy={}
        if config is not None:
            if 'root' in config and Path(config['root']).resolve()!=self.root.resolve():
                raise ValueError('Session root mismatch')
            extended=(config.get('session')=='2026-09-21-deep-dive' and self.root.resolve()==(BASE/'data'/'session-2026-09-21-deep-dive').resolve())
            ceiling=10000 if extended else 1000
            if not isinstance(config.get('helius_credit_cap'),int) or not 0<config['helius_credit_cap']<=ceiling:
                raise ValueError('Invalid session credit cap')
            if config.get('request_policy'):
                if not extended:raise ValueError('Extended request policy requires the explicitly authorized deep-dive session')
                self.request_policy=dict(config['request_policy'])
                if not 1<=self.request_policy.get('max_history_records',0)<=1000 or not 1<=self.request_policy.get('max_history_interval_seconds',0)<=259200:
                    raise ValueError('Invalid extended request policy')
            caps=config.get('credit_buckets',{})
            if not caps or any(not isinstance(v,int) or v<=0 for v in caps.values()) or sum(caps.values())>config['helius_credit_cap']:
                raise ValueError('Invalid session bucket caps')
            self.caps=dict(caps);self.cap=config['helius_credit_cap']
            configured=config.get('acquisition_deadline_at',config.get('deadline_at'))
            if not configured:raise ValueError('Session deadline required')
            session_end=dt.datetime.fromisoformat(config['deadline_at'].replace('Z','+00:00'))
            acquisition_end=dt.datetime.fromisoformat(configured.replace('Z','+00:00'))
            if session_end.tzinfo is None or acquisition_end.tzinfo is None:
                raise ValueError('Timezone-aware deadline required')
            if acquisition_end>session_end:raise ValueError('Acquisition cutoff exceeds session deadline')
            # A caller may tighten, never extend, the frozen deadline.
            if deadline:
                if dt.datetime.fromisoformat(deadline.replace('Z','+00:00'))>dt.datetime.fromisoformat(configured.replace('Z','+00:00')):
                    raise ValueError('Cannot extend frozen session deadline')
            else:deadline=configured
            self.cache_roots+=tuple(Path(p) for p in config.get('cache_roots',[]))
        self.deadline=dt.datetime.fromisoformat(deadline.replace('Z','+00:00')) if deadline else None
        if self.deadline and self.deadline.tzinfo is None:raise ValueError('Timezone-aware deadline required')

    def call(self,method,params,bucket='state',purpose=''):
        estimate=cost(method,params,self.request_policy)
        if self.config and self.config.get('session')=='2026-09-21-deep-dive':
            bounds=params[1].get('filters',{}).get('blockTime',{}) if method=='getTransactionsForAddress' else {}
            held=self.config.get('cohort',{}).get('holdout',{})
            intersects=bool(bounds and held and bounds['gte']<held['lt']+900 and bounds['lt']>held['gte'])
            if bucket=='holdout' or intersects:
                from deep_experiment import verify_lock
                verify_lock()
        request={'jsonrpc':'2.0','id':'research','method':method,'params':params}
        key=digest(request);target=self.root/(key+'.json')
        with (self.root/'capture.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            for candidate in [target,*(p/(key+'.json') for p in self.cache_roots)]:
                if candidate.exists():
                    cached=json.loads(candidate.read_text())
                    if cached['request']!=request or digest(cached['response'])!=cached['response_sha256']:
                        raise ValueError('Cache integrity failed')
                    return cached
            if self.config is None:raise ValueError('Explicit valid session configuration required before dispatch')
            if bucket not in self.caps:raise ValueError('Unknown credit bucket')
            if bucket=='contingency' and not purpose.startswith('DIAGNOSED:'):
                raise ValueError('Contingency requires recorded diagnosed evidence need')
            if (self.root/'session_completion.json').exists():
                raise ValueError('Research session closed; cache-only reproduction remains available')
            if self.deadline and dt.datetime.now(dt.timezone.utc)>=self.deadline:
                raise ValueError('Frozen research session expired; cache-only reproduction remains available')
            ledger=self.root/'credits.jsonl'
            entries=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
            prior=[e for e in entries if e['request_key']==key]
            retry_reason=self.retry_authorizations.get(key)
            if prior and not (len(prior)==1 and isinstance(retry_reason,str) and retry_reason.strip()):
                raise ValueError('Prior dispatch unresolved; no automatic retry')
            if sum(e['reserved_credits'] for e in entries)+estimate>self.cap:raise ValueError('Session credit cap')
            if sum(e['reserved_credits'] for e in entries if e['bucket']==bucket)+estimate>self.caps[bucket]:raise ValueError('Bucket credit cap')
            import os
            with ledger.open('a') as stream:
                stream.write(stable({'request_key':key,'request':request,'bucket':bucket,'purpose':purpose,'reserved_credits':estimate,'reserved_at':stamp(),
                                    'attempt':len(prior)+1,'manual_retry_reason':retry_reason if prior else None})+'\n')
                stream.flush();os.fsync(stream.fileno())
            try:
                response=self.transport(request)
                if 'error' in response:
                    # Provider messages may echo URLs/credentials. Persist code
                    # only; explicitly distinguish this redacted diagnostic from
                    # an immutable successful raw response. Never auto-retry.
                    code=response['error'].get('code') if isinstance(response['error'],dict) else None
                    message=str(response['error'].get('message','')).lower() if isinstance(response['error'],dict) else ''
                    failure={'request_key':key,'request':request,'retrieved_at':stamp(),
                             'status':'rpc_rejected','provider_error_code':code if isinstance(code,int) else None,
                             'provider_error_categories':[word for word in ('unsupported','invalid','token','rate limit','time range','blocked','index','timeout','too many','not supported','api key','limit','address') if word in message],
                             'provider_message_retained':False,'raw_response_retained':False,
                             'reason':'Provider error text excluded to prevent credential/URL leakage'}
                    with (self.root/(key+'.failure.json')).open('x') as stream:stream.write(json.dumps(failure,indent=2)+'\n')
                    raise ValueError('RPC rejected request')
                if 'result' not in response:raise ValueError('Malformed RPC response')
            except Exception as exc:
                # Never serialize an exception message, URL, headers or credential.
                raise RuntimeError('Capture failed: '+type(exc).__name__) from None
            capture={'request':request,'response':response,'retrieved_at':stamp(),
                     'response_sha256':digest(response),'estimated_credits':estimate,'request_key':key}
            with target.open('x') as stream:stream.write(json.dumps(capture,indent=2)+'\n')
            return capture

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--windows',action='store_true');parser.add_argument('--blocks',action='store_true')
    parser.add_argument('--close-pages',action='store_true');parser.add_argument('--diagnose-log',action='store_true')
    args=parser.parse_args();client=Capture()
    old=BASE/'data'/'helius-pilot-2026-09-16'
    specifications=[('loss','losing_cycle_market',1782328168,1782328219),('winner','winner_entry_curve',1782326684,1782326771)]
    if args.close_pages:
        # One continuation per original interval, never an unbounded page loop.
        origins=[]
        for path in [old/'losing_cycle_market.json',old/'winner_entry_curve.json',*sorted(OUT.glob('*.json'))]:
            data=json.loads(path.read_text())
            if not isinstance(data,dict) or data.get('request',{}).get('method')!='getTransactionsForAddress':continue
            if data['request']['params'][0] not in {json.loads((old/(n+'.json')).read_text())['request']['params'][0] for n in ('losing_cycle_market','winner_entry_curve')}:continue
            if 'paginationToken' in data['request']['params'][1]:continue
            origins.append(data)
        if len(origins)>10:raise ValueError('Unexpected origin count; inspect before spending')
        for origin in origins:
            token=origin['response']['result'].get('paginationToken')
            if not token:continue
            params=json.loads(json.dumps(origin['request']['params']))
            params[1]['paginationToken']=token
            c=client.call('getTransactionsForAddress',params,purpose='Confirm bounded interval exhaustion; do not infer from short page')
            print(json.dumps({'closure':c['request_key'],'count':len(c['response']['result']['data']),'next':bool(c['response']['result'].get('paginationToken'))}),flush=True)
    if args.diagnose_log:
        c=client.call('getTransaction',['335cgm4nVceZ7h34CtcL9ZbAK1zB16pBSkeqq6mLhkGj8d7Fg4ThgZZGs7fU3z51apyaUcz31owmjP85ni4UrEQ8',
                      {'encoding':'jsonParsed','maxSupportedTransactionVersion':0}],bucket='gaps',purpose='One diagnostic fetch: test whether archived transaction logs are also truncated')
        raw=c['response']['result']
        print(json.dumps({'log_diagnostic':c['request_key'],'truncated':None if raw is None else any('truncat' in x.lower() for x in raw['meta']['logMessages'])}),flush=True)
    if args.windows:
        plans=[]
        for label,source,start,end in specifications:
            reserve=json.loads((old/(source+'.json')).read_text())['request']['params'][0]
            for left in range(start,end,20):
                right=min(left+20,end)
                plans.append({'label':label,'reserve':reserve,'start':left,'end':right})
        plan_path=OUT/'window_plan.json'
        if not plan_path.exists():plan_path.write_text(json.dumps(plans,indent=2)+'\n')
        for plan in plans:
            c=client.call('getTransactionsForAddress',[plan['reserve'],{'transactionDetails':'full','encoding':'jsonParsed',
                 'maxSupportedTransactionVersion':0,'limit':100,'sortOrder':'asc','filters':{'blockTime':{'gte':plan['start'],'lt':plan['end']}}}],purpose='Frozen entry/exit coverage '+plan['label'])
            rows=c['response']['result']['data']
            print(json.dumps({'label':plan['label'],'start':plan['start'],'end':plan['end'],'count':len(rows),'key':c['request_key']}))
    if args.blocks:
        # Only ambiguous same-slot successful curve events, not whole-history blocks.
        from decode_curve_state_events import events
        byslot={}
        for path in [old/'losing_cycle_market.json',old/'winner_entry_curve.json',*OUT.glob('*.json')]:
            data=json.loads(path.read_text())
            if not isinstance(data,dict) or data.get('request',{}).get('method')!='getTransactionsForAddress':continue
            if data['request']['params'][0] not in {json.loads((old/(n+'.json')).read_text())['request']['params'][0] for n in ('losing_cycle_market','winner_entry_curve')}:continue
            for raw in data['response']['result']['data']:
                if events(raw):byslot.setdefault(raw['slot'],set()).add(raw['transaction']['signatures'][0])
        for slot,sigs in sorted(byslot.items()):
            if len(sigs)>1:
                c=client.call('getBlock',[slot,{'transactionDetails':'signatures','rewards':False,'maxSupportedTransactionVersion':0}],purpose='Resolve material same-slot event order')
                print(json.dumps({'slot':slot,'matched':sum(s in c['response']['result']['signatures'] for s in sigs),'expected':len(sigs)}))

if __name__=='__main__':main()
