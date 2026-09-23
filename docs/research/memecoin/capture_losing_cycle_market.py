"""One cache-first market-history query, maximum 100 full transactions/10 estimated credits.

Purpose: obtain independent market trades around the verified 61-second losing
cycle. Window and reserve are derived only from previously captured evidence.
No pagination, retries, trading, or deployment.
"""
import datetime as dt
import json
import pathlib
import tomllib
import urllib.request
from decode_cached_history import ROOT

def main():
    mint='435CfmvrJ4QtkVv4cZ1TbUa7rzrKKjvQJLMnvhTCpump'
    rows=[json.loads(line) for line in (ROOT/'reserve_pair_evidence.jsonl').read_text().splitlines()]
    events=[r for r in rows if r['mint']==mint]
    addresses={r['reserve_authority'] for r in events}
    assert len(addresses)==1 and len(events)==2
    address=next(iter(addresses))
    start=min(r['block_time'] for r in events)-5
    end=max(r['block_time'] for r in events)+31
    body={'jsonrpc':'2.0','id':'losing-cycle-market','method':'getTransactionsForAddress',
          'params':[address,{'transactionDetails':'full','encoding':'jsonParsed','maxSupportedTransactionVersion':0,
                             'limit':100,'sortOrder':'asc','filters':{'blockTime':{'gte':start,'lt':end}}}]}
    path=ROOT/'losing_cycle_market.json'
    manifest={'purpose':'Market trades from 5s before first owner buy to 30s after final sell',
              'request':body,'max_requests':1,'estimated_credit_cap':10,'mint':mint}
    (ROOT/'losing_cycle_market_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    cached=path.exists()
    if cached:
        capture=json.loads(path.read_text())
        assert capture['request']==body
    else:
        config=tomllib.loads(pathlib.Path('/Users/jhonny/.codex/config.toml').read_text())
        key=config['mcp_servers']['helius']['env']['HELIUS_API_KEY']
        request=urllib.request.Request('https://mainnet.helius-rpc.com/?api-key='+key,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=30) as response:payload=json.load(response)
        except Exception as exc:
            print(json.dumps({'error_type':type(exc).__name__}));return 1
        if 'error' in payload:
            print(json.dumps({'rpc_error_code':payload['error'].get('code')}));return 1
        capture={'request':body,'response':payload,'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat()}
        path.write_text(json.dumps(capture,indent=2)+'\n')
    data=capture['response']['result']['data']
    print(json.dumps({'records':len(data),'cached':cached,'estimated_new_credits':0 if cached else 10,
                      'oldest_time':min((r['blockTime'] for r in data),default=None),
                      'newest_time':max((r['blockTime'] for r in data),default=None),
                      'requested_end':end,'pagination_cursor_present':bool(capture['response']['result'].get('paginationToken'))}))
    return 0

if __name__=='__main__':raise SystemExit(main())
