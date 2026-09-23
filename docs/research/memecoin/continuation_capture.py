"""Bounded, alternating continuation pages. No unattended or persistent work."""
import copy
import datetime as dt
import json
from pathlib import Path
from pilot_capture import Capture, OUT, digest, stamp
from continuation_session import ROOT, MANIFEST, CATE_KEYS, UNIPCS, save_new

def load_capture(path):
    capture=json.loads(Path(path).read_text())
    if digest(capture['response'])!=capture['response_sha256']:
        raise ValueError('Capture integrity failure')
    return capture

def summarize_chain(captures):
    if not captures:return {'complete':False,'reason':'No capture','records':0,'failed':0,'rows':[]}
    request=captures[0]['request'];address,options=request['params']
    base=copy.deepcopy(options);base.pop('paginationToken',None)
    seen={};tokens=set();previous_token=None;complete=False
    for index,capture in enumerate(captures):
        addr,opts=capture['request']['params'];shape=copy.deepcopy(opts);token=shape.pop('paginationToken',None)
        if addr!=address or shape!=base:raise ValueError('Pagination filters changed')
        if index and token!=previous_token:raise ValueError('Broken pagination chain')
        result=capture['response']['result']
        if not isinstance(result,dict) or not isinstance(result.get('data'),list):raise ValueError('Malformed history response')
        for row in result['data']:
            if not isinstance(row.get('blockTime'),int):raise ValueError('Unknown event time')
            bounds=base['filters']['blockTime']
            if not bounds['gte']<=row['blockTime']<bounds['lt']:raise ValueError('Record outside frozen interval')
            key=('solana-mainnet',row['transaction']['signatures'][0]);hashed=digest(row)
            if key in seen and seen[key][0]!=hashed:raise ValueError('Conflicting duplicate signature')
            seen[key]=(hashed,row,capture['request_key'],capture['retrieved_at'])
        previous_token=result.get('paginationToken')
        if previous_token:
            if previous_token in tokens:raise ValueError('Repeated pagination cursor')
            tokens.add(previous_token)
        else:
            if index!=len(captures)-1:raise ValueError('Page after cursor exhaustion')
            complete=True
    rows=[dict(raw=r,source_capture=key,retrieved_at=retrieved,available_at=None)
          for _,r,key,retrieved in seen.values()]
    # This is a display order, not an assertion of same-slot instruction order.
    rows.sort(key=lambda r:(r['raw']['slot'],r['raw'].get('transactionIndex',-1),r['raw']['transaction']['signatures'][0]))
    return dict(complete=complete,reason='Provider-reported cursor exhaustion' if complete else 'Unexhausted cursor',
        address=address,interval=base['filters']['blockTime'],pages=len(captures),records=len(rows),
        failed=sum(r['raw']['meta']['err'] is not None for r in rows),
        first_event_time=min((r['raw']['blockTime'] for r in rows),default=None),
        last_event_time=max((r['raw']['blockTime'] for r in rows),default=None),
        source_captures=[c['request_key'] for c in captures],rows=rows)

def collect(kind,transport_recovery=False):
    manifest=json.loads(MANIFEST.read_text())
    retries=json.loads((ROOT/'transport_recovery.json').read_text())['one_time_request_authorizations'] if transport_recovery else None
    client=Capture(ROOT,config=manifest,retry_authorizations=retries)
    if kind=='cate':
        chains=[[load_capture(OUT/(key+'.json'))] for key in CATE_KEYS]
        counts=[0,0];stops=[None,None];bucket='discovery';max_pages=20
    elif kind=='unipcs':
        params=[UNIPCS,{'transactionDetails':'full','encoding':'jsonParsed','maxSupportedTransactionVersion':1,
                'limit':100,'sortOrder':'asc','filters':{'blockTime':manifest['unipcs_interval'],
                                                       'status':'any','tokenAccounts':'all'}}]
        try:
            first=client.call('getTransactionsForAddress',params,bucket='wallets',purpose='Frozen five-minute Unipcs wallet and owned-token-account activity')
        except (ValueError,RuntimeError) as exc:
            save_new(ROOT/'unipcs_capture_failure.json',{'reason':str(exc),'at':stamp()});return
        chains=[[first]];counts=[1];stops=[None];bucket='wallets';max_pages=20
    else:raise ValueError('Unknown acquisition scope')
    # At most 40 discovery pages / 20 wallet pages, alternating discovery origins.
    for round_index in range(max_pages):
        active=False
        for index,chain in enumerate(chains):
            if stops[index]:continue
            try:
                summary=summarize_chain(chain)
                if summary['complete']:stops[index]='exhausted';continue
                if counts[index]>=max_pages:stops[index]='page_cap';continue
                if dt.datetime.now(dt.timezone.utc)>=dt.datetime.fromisoformat(manifest['acquisition_deadline_at'].replace('Z','+00:00')):
                    stops[index]='acquisition_deadline';continue
                params=copy.deepcopy(chain[0]['request']['params'])
                params[1]['paginationToken']=chain[-1]['response']['result']['paginationToken']
                capture=client.call('getTransactionsForAddress',params,bucket=bucket,
                    purpose=f'Frozen {kind} interval {index}: continuation page {counts[index]+1}')
                chain.append(capture);counts[index]+=1;active=True
                # Validate immediately, before requesting another page.
                summary=summarize_chain(chain)
                print(json.dumps({'scope':kind,'interval':index,'new_pages':counts[index],
                    'records':summary['records'],'failed':summary['failed'],'complete':summary['complete']}),flush=True)
            except (ValueError,RuntimeError,KeyError) as exc:
                stops[index]=str(exc)
        if not active:break
    output=[]
    for index,chain in enumerate(chains):
        try:summary=summarize_chain(chain)
        except ValueError as exc:
            summary={'complete':False,'reason':str(exc),'source_captures':[c['request_key'] for c in chain]}
        summary.pop('rows',None)
        summary.update(new_pages=counts[index],stop_reason=stops[index] or ('exhausted' if summary['complete'] else 'page_cap'))
        output.append(summary)
    suffix='_resumed' if transport_recovery else ''
    save_new(ROOT/(kind+suffix+'_coverage.json'),{'scope':kind,'created_at':stamp(),'intervals':output})

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('scope',choices=['cate','unipcs'])
    parser.add_argument('--transport-recovery',action='store_true')
    args=parser.parse_args();collect(args.scope,args.transport_recovery)
