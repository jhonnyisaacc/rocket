"""Small immutable primary-source archive, inert bytes only."""
import hashlib
import urllib.request
from continuation_session import ROOT,save_new
from pilot_capture import stamp

URLS={
 'helius_history.md':'https://www.helius.dev/docs/rpc/gettransactionsforaddress.md',
 'helius_credits.md':'https://www.helius.dev/docs/billing/credits.md',
 'anchor_events.html':'https://www.anchor-lang.com/docs/features/events',
 'anchor_event_macro.rs':'https://raw.githubusercontent.com/otter-sec/anchor/62865c636aecc6974fc9cfebfc6cf08ca4f0bb72/lang/attribute/event/src/lib.rs',
 'anchor_event_tag.rs':'https://raw.githubusercontent.com/otter-sec/anchor/62865c636aecc6974fc9cfebfc6cf08ca4f0bb72/lang/src/event.rs'
}

def main():
    root=ROOT/'sources';root.mkdir(exist_ok=True);sources=[]
    for name,url in URLS.items():
        path=root/name
        if path.exists():raise ValueError('Source archive already exists; do not overwrite')
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'memecoin-research/1.0'}),timeout=20) as response:
                content=response.read()
            with path.open('xb') as stream:stream.write(content)
            sources.append({'file':name,'url':url,'sha256':hashlib.sha256(content).hexdigest(),'retrieved_at':stamp()})
        except Exception as exc:
            sources.append({'file':name,'url':url,'unavailable':type(exc).__name__,'retrieved_at':stamp()})
    save_new(root/'manifest.json',{'sources':sources,'new_helius_credits':0})
    print('Primary source records:',len(sources))

if __name__=='__main__':main()
