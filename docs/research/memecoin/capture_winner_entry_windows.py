"""Two targeted entry windows, <=200 full records, estimated <=20 credits.
No pagination. Cache first; public-chain read only. Largest historical cashflow
group is deliberately selected as a diagnostic case, not an unbiased sample.
"""
import json
import datetime as dt
import pathlib
import tomllib
import urllib.request
from decode_cached_history import ROOT

def main():
    mint='EcPhZph4VXgHW279x5bYX2VjvWBHW5TTQingCAtEpump'
    events=[json.loads(l) for l in (ROOT/'reserve_pair_evidence.jsonl').read_text().splitlines()]
    buys=[r for r in events if r['mint']==mint and r['owner_token_delta_raw']>0]
    assert len(buys)==2
    for entry in sorted(buys,key=lambda r:r['block_time']):
        label='winner_entry_'+('amm' if entry['reserve_in_amm_instruction'] else 'curve')
        path=ROOT/(label+'.json')
        body={'jsonrpc':'2.0','id':label,'method':'getTransactionsForAddress','params':[entry['reserve_authority'],
              {'transactionDetails':'full','encoding':'jsonParsed','maxSupportedTransactionVersion':0,'limit':100,'sortOrder':'asc',
               'filters':{'blockTime':{'gte':entry['block_time']-2,'lt':entry['block_time']+36}}}]}
        manifest={'request':body,'anchor':entry,'max_requests':1,'estimated_credit_cap':10,'purpose':'Observed reserve ratio probes at 5/15/30s after this entry; not follower fills'}
        (ROOT/(label+'_manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
        cached=path.exists()
        if cached:
            capture=json.loads(path.read_text());assert capture['request']==body
        else:
            config=tomllib.loads(pathlib.Path('/Users/jhonny/.codex/config.toml').read_text())
            key=config['mcp_servers']['helius']['env']['HELIUS_API_KEY']
            req=urllib.request.Request('https://mainnet.helius-rpc.com/?api-key='+key,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(req,timeout=30) as response:payload=json.load(response)
            except Exception as exc:
                print(json.dumps({'error_type':type(exc).__name__}));return 1
            if 'error' in payload:
                print(json.dumps({'rpc_error_code':payload['error'].get('code')}));return 1
            capture={'request':body,'response':payload,'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat()}
            path.write_text(json.dumps(capture,indent=2)+'\n')
        rows=capture['response']['result']['data']
        print(json.dumps({'label':label,'cached':cached,'estimated_new_credits':0 if cached else 10,'records':len(rows),
                          'newest_time':max((r['blockTime'] for r in rows),default=None),'anchor_time':entry['block_time']}))
    return 0

if __name__=='__main__':raise SystemExit(main())
