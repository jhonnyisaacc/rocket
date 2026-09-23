"""One bounded, cache-first query around a publicly observed Fomo fill."""
import datetime as dt
import json
import pathlib
import tomllib
import urllib.request
import argparse
from decode_cached_history import ROOT, decode

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fill', choices=['aug30', 'aug25'], default='aug30')
    args = parser.parse_args()
    target = ROOT / ('unipcs_useless_' + args.fill + '.json')
    start, end = (29, None) if args.fill == 'aug30' else (25, 27)
    owner = '2heJbC32Tpfcb3nbUb5ER61K11FGZVfVGtVnDm6LDogF'
    account = '4rEBXtajXWiSMH6ogp6mZGcu7yRKrUer3ykWSSvQse2A'
    body = {'jsonrpc': '2.0', 'id': 'fomo-fill-verification', 'method': 'getTransactionsForAddress',
            'params': [account, {'transactionDetails': 'full', 'encoding': 'jsonParsed',
                       'maxSupportedTransactionVersion': 0, 'limit': 100, 'sortOrder': 'asc',
                       'filters': {'blockTime': {'gte': int(dt.datetime(2026,8,start,tzinfo=dt.timezone.utc).timestamp()),
                                                'lt': int((dt.datetime(2026,8,end,tzinfo=dt.timezone.utc) if end else dt.datetime(2026,9,1,tzinfo=dt.timezone.utc)).timestamp())}}}]}
    cached = target.exists()
    if cached:
        capture = json.loads(target.read_text())
    else:
        config = tomllib.loads(pathlib.Path('/Users/jhonny/.codex/config.toml').read_text())
        key = config['mcp_servers']['helius']['env']['HELIUS_API_KEY']
        req = urllib.request.Request('https://mainnet.helius-rpc.com/?api-key=' + key,
                                     data=json.dumps(body).encode(), headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.load(response)
        except Exception as exc:
            print(json.dumps({'error_type':type(exc).__name__}))
            return 1
        if 'error' in payload:
            print(json.dumps({'rpc_error_code':payload['error'].get('code')}))
            return 1
        capture = {'request':body, 'response':payload, 'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat()}
        target.write_text(json.dumps(capture, indent=2)+'\n')
    result = capture['response']['result']
    rows = [decode(r, owner) for r in result['data']]
    (ROOT / ('unipcs_useless_' + args.fill + '_ledger.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
    print(json.dumps({'cached':cached, 'estimated_new_credits':0 if cached else 10,
                      'pagination_cursor_present':bool(result.get('paginationToken')), 'records':len(rows),
                      'two_sided_flows':[r for r in rows if r['category']=='two_sided_token_flow_unverified']}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
