"""Frozen bounded query registry; every dispatch uses the session credit guard."""
import copy
import json
from deep_session import ROOT, MANIFEST, PUMP, SEEDS, save_new
from pilot_capture import Capture, digest, stamp
from continuation_capture import summarize_chain

def query(name,address,interval,bucket,pages=1,limit=1000,token_accounts='none'):
    spec=dict(name=name,address=address,interval=interval,bucket=bucket,page_cap=pages,
              limit=limit,token_accounts=token_accounts,purpose=name)
    directory=ROOT/'queries';directory.mkdir(exist_ok=True)
    path=directory/(name+'.json')
    if path.exists():
        if json.loads(path.read_text())!=spec:raise ValueError('Frozen query changed')
    else:save_new(path,spec)
    if 'holdout' in name or bucket=='holdout':
        if not (ROOT/'holdout_lock.json').exists():raise ValueError('Holdout locked')
        from deep_experiment import verify_lock
        verify_lock()
    client=Capture(ROOT,config=json.loads(MANIFEST.read_text()))
    options=dict(transactionDetails='full',encoding='jsonParsed',maxSupportedTransactionVersion=1,
                 limit=limit,sortOrder='asc',filters=dict(blockTime=interval,status='any',tokenAccounts=token_accounts))
    chain=[];stop='page_cap'
    for page in range(pages):
        try:
            capture=client.call('getTransactionsForAddress',[address,copy.deepcopy(options)],bucket=bucket,purpose=name)
            chain.append(capture);summary=summarize_chain(chain)
            print(json.dumps(dict(query=name,page=page+1,records=summary['records'],complete=summary['complete'])),flush=True)
            if summary['complete']:stop='exhausted';break
            options['paginationToken']=capture['response']['result']['paginationToken']
        except (ValueError,RuntimeError,KeyError) as exc:
            stop=type(exc).__name__+': '+str(exc);break
    try:summary=summarize_chain(chain)
    except (ValueError,KeyError) as exc:summary=dict(complete=False,reason=str(exc),rows=[])
    summary.pop('rows',None)
    summary.update(stop_reason=stop,query=spec,observed_at=stamp(),source_captures=[c['request_key'] for c in chain])
    output=directory/(name+'.coverage.json')
    if not output.exists():save_new(output,summary)
    return chain

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('scope',choices=['seeds','development-cohort','development-activity','holdout-cohort','holdout-activity'])
    a=p.parse_args();m=json.loads(MANIFEST.read_text())
    if a.scope=='seeds':
        for name,address in SEEDS.items():query('seed-'+name,address,m['seed_history_interval'],'wallets',4,1000,'all')
    elif a.scope.endswith('-cohort'):
        split=a.scope.split('-')[0];query(split+'-cohort',PUMP,m['cohort'][split],'cohort',10)
    else:
        split=a.scope.split('-')[0];panel=json.loads((ROOT/(split+'_cohort_v2.json')).read_text())
        for e in panel['selected']:
            query(split+'-'+e['mint'],e['bonding_curve'],{'gte':e['timestamp'],'lt':e['timestamp']+900},split,2 if split=='development' else 1)
