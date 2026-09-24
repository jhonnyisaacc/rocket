"""Reproduce the bounded public-profile evidence panel from local captures.

Net-flow candidates are NOT attributed to a Fomo identity and are NOT verified
trades. No wallet is promoted from approximate dollar amounts or timing alone.
"""
import json
from collections import defaultdict
from pilot_capture import BASE, OUT, digest

MINT='Ai66LHZG9MCzg1WKdawwqduVAXpNDUuV8M3uyq5ppump'
USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'


def build_discovery():
    panel=json.loads((BASE/'session_20260921_candidates.json').read_text())
    candidate=next(c for c in panel['candidates'] if c['name']=='GMannnnn')
    inventory=[];flows=[];seen=set()
    for key in candidate['captures']:
        capture=json.loads((OUT/(key+'.json')).read_text())
        if digest(capture['response'])!=capture['response_sha256']:
            raise ValueError('Discovery capture integrity failure')
        rows=capture['response']['result']['data']
        inventory.append(dict(capture=key,rows=len(rows),failed=sum(r['meta']['err'] is not None for r in rows),
                              first_event_time=min((r['blockTime'] for r in rows),default=None),
                              last_event_time=max((r['blockTime'] for r in rows),default=None),
                              requested_interval=capture['request']['params'][1]['filters']['blockTime'],
                              retrieved_at=capture['retrieved_at'],available_at=None,
                              cursor_present=bool(capture['response']['result'].get('paginationToken')),
                              complete=False,reason='At record limit; pagination deliberately not expanded'))
        for raw in rows:
            signature=raw['transaction']['signatures'][0]
            if signature in seen:continue
            seen.add(signature)
            if raw['meta']['err'] is not None:continue
            changes=defaultdict(int)
            for side,sign in [('preTokenBalances',-1),('postTokenBalances',1)]:
                for b in raw['meta'].get(side,[]):
                    changes[(b.get('owner'),b['mint'])]+=sign*int(b['uiTokenAmount']['amount'])
            signers=[k['pubkey'] for k in raw['transaction']['message']['accountKeys'] if k.get('signer')]
            for owner in signers:
                tokens=changes[(owner,MINT)];quote=changes[(owner,USDC)]
                if tokens>0 and quote<=-1_000_000_000:
                    flows.append(dict(signature=signature,owner=owner,token_credit_raw=tokens,usdc_debit_raw=-quote,
                                      event_time=raw['blockTime'],retrieved_at=capture['retrieved_at'],available_at=None,
                                      capture=key,classification='buy_like_net_flow_unverified',
                                      social_identity=None,attribution_status='not_admitted',
                                      reason='No exact reconciliation with frozen public Fomo fill evidence'))
    return dict(edge='NO_EDGE_VALIDATED',candidate_panel=panel,capture_inventory=inventory,
                unique_transactions=len(seen),unattributed_flows=flows,new_admitted_wallet_mappings=0,
                selection_is_convenience_sample=True,historical_identity_available_at=None)


def main():
    report=build_discovery()
    (OUT/'discovery_evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(profiles=len(report['candidate_panel']['candidates']),transactions=report['unique_transactions'],
                          unattributed_flows=len(report['unattributed_flows']),new_mappings=0)))


if __name__=='__main__':main()
