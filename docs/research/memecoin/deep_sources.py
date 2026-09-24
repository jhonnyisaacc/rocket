"""Immutable primary-source retrieval; no Helius credits or executable downloads."""
import hashlib
import urllib.request
from deep_session import ROOT, save_new
from pilot_capture import stamp

SOURCES={
 'pump_september_idl.json':'https://raw.githubusercontent.com/pump-fun/pump-public-docs/e0687ae9b7e064a0f54efc7297c65eecfbba3a8f/idl/pump.json',
 'memetrans_v1.html':'https://arxiv.org/html/2602.13480v1',
 'midsummer_v1.html':'https://arxiv.org/html/2507.01963v1',
 'backtest_probability.pdf':'https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf'}

if __name__=='__main__':
    folder=ROOT/'sources';folder.mkdir(exist_ok=True)
    for name,url in SOURCES.items():
        path=folder/name
        if path.exists():continue
        with urllib.request.urlopen(url,timeout=30) as r:body=r.read()
        with path.open('xb') as f:f.write(body)
        save_new(folder/(name+'.provenance.json'),dict(url=url,retrieved_at=stamp(),sha256=hashlib.sha256(body).hexdigest()))
        print(name,len(body),flush=True)
