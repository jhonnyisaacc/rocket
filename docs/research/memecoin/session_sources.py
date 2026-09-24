"""Capture primary docs as inert evidence; never execute downloaded code."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.request
import base64
import io
import tarfile

OUT=Path(__file__).resolve().parent/'data'/'session-2026-09-21'/'sources'
URLS={
 'pump_buy.md':'https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/docs/instructions/BUY.md',
 'pump_sell.md':'https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/docs/instructions/SELL.md',
 'pump_fees.md':'https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/docs/FEE_PROGRAM_README.md',
 'pump_recipients.md':'https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/docs/FEE_RECIPIENTS.md',
 'pump_idl.json':'https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/idl/pump.json',
 'sdk_metadata.json':'https://registry.npmjs.org/@pump-fun/pump-sdk/latest',
 'docs_commit.json':'https://api.github.com/repos/pump-fun/pump-public-docs/commits/main',
 'pump_cashback.md':'https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/docs/PUMP_CASHBACK_README.md',
 'claim_cashback.md':'https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/docs/instructions/CLAIM_CASHBACK.md',
 'historical_commits.json':'https://api.github.com/repos/pump-fun/pump-public-docs/commits?until=2026-06-24T00:00:00Z&per_page=1',
 'historical_pump_idl.json':'https://raw.githubusercontent.com/pump-fun/pump-public-docs/1b822158844a60ca577df6ca122211b595a1a578/idl/pump.json',
 'historical_cashback.md':'https://raw.githubusercontent.com/pump-fun/pump-public-docs/1b822158844a60ca577df6ca122211b595a1a578/docs/PUMP_CASHBACK_README.md',
 'helius_history.md':'https://www.helius.dev/docs/rpc/gettransactionsforaddress.md',
 'helius_credits.md':'https://www.helius.dev/docs/billing/credits.md',
 'jito_execution.html':'https://docs.jito.wtf/lowlatencytxnsend/',
}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for name,url in URLS.items():
        target=OUT/name
        if not target.exists():
            req=urllib.request.Request(url,headers={'User-Agent':'memecoin-research/1.0'})
            with urllib.request.urlopen(req,timeout=25) as res:content=res.read()
            target.write_bytes(content)
        raw=target.read_bytes()
        manifest.append({'file':name,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
    (OUT/'manifest.json').write_text(json.dumps({'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'sources':manifest},indent=2)+'\n')
    metadata=json.loads((OUT/'sdk_metadata.json').read_text())
    package=OUT/'pump-sdk.tgz'
    if not package.exists():
        with urllib.request.urlopen(metadata['dist']['tarball'],timeout=25) as res:raw=res.read()
        expected=metadata['dist']['integrity'].split('-',1)[1]
        assert base64.b64encode(hashlib.sha512(raw).digest()).decode()==expected
        package.write_bytes(raw)
    if base64.b64encode(hashlib.sha512(package.read_bytes()).digest()).decode()!=metadata['dist']['integrity'].split('-',1)[1]:
        raise ValueError('Cached SDK integrity mismatch')
    manifest.append({'file':package.name,'url':metadata['dist']['tarball'],
                     'sha256':hashlib.sha256(package.read_bytes()).hexdigest(),
                     'sha512_integrity':metadata['dist']['integrity'],'version':metadata['version'],
                     'bytes':package.stat().st_size})
    (OUT/'manifest.json').write_text(json.dumps({'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'sources':manifest},indent=2)+'\n')
    # Inspect inert text only, no npm install or lifecycle scripts.
    with tarfile.open(fileobj=io.BytesIO(package.read_bytes()),mode='r:gz') as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.endswith('index.js'):
                dest=OUT/('sdk_'+member.name.replace('/','_'))
                if not dest.exists():dest.write_bytes(archive.extractfile(member).read())
        print('package_members', [m.name for m in archive.getmembers()])
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
