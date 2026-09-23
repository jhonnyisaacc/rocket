"""Reports and real OHLC charts, never generated market imagery."""
import csv,hashlib,json,math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from engine import H,D,W,MONDAY,available_context,inside,intersects

def read(p):return json.loads(p.read_text())
def save(p,o):p.write_text(json.dumps(o,indent=2,sort_keys=True,allow_nan=False)+'\n')
def utc(t):return datetime.fromtimestamp(t/1000,timezone.utc).isoformat()

def chart(root,coin,bars,f,name,forward=0,trade=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    cutoff=f['time'];shown=[b for b in bars if cutoff-72*4*H<=b['t'] and b['t']+4*H<=cutoff+forward*4*H]
    fig,ax=plt.subplots(figsize=(13,6.5));fig.patch.set_facecolor('#fafbfc')
    width=.12
    for b in shown:
        x=mdates.date2num(datetime.fromtimestamp(b['t']/1000,timezone.utc));color='#11856f' if b['c']>=b['o'] else '#c74646'
        ax.plot([x,x],[b['l'],b['h']],color=color,lw=.7)
        ax.add_patch(Rectangle((x-width/2,min(b['o'],b['c'])),width,max(abs(b['c']-b['o']),abs(b['c'])*.00001),color=color))
    z=f.get('candidate')
    if z:
        if not trade:ax.axhspan(*z['band'],color='#69a7e8',alpha=.13,label='75–86% daily-impulse band')
        ax.axhspan(*z['zone'],color='#eab32c',alpha=.7,label='Legacy six-candle proxy zone' if trade else 'Frozen candidate BEN intersection')
        if not trade:ax.scatter([mdates.date2num(datetime.fromtimestamp(z['pivot']['t']/1000,timezone.utc))],[z['pivot']['price']],marker='o',color='#233d84',s=35,label='Confirmed zone swing')
    if f.get('leg'):
        for key,col in [('origin','#ab3040'),('terminal','#556677')]:
            label='Impulse '+key+(' (unconfirmed)' if key=='terminal' and not f['leg']['confirmed'] else '')
            ax.axhline(f['leg'][key],color=col,ls='--',lw=.8,label=label)
    for i,target in enumerate(f.get('targets',[])):ax.axhline(target,color='#6c4c9a',ls=':',lw=.8,label=f'Structural objective {i+1}')
    x=mdates.date2num(datetime.fromtimestamp(cutoff/1000,timezone.utc));ax.axvline(x,color='#222',lw=1,label='Decision / earliest future execution')
    if trade:
        for key,col in [('entry','#116633'),('stop','#aa2233'),('target','#773399')]:
            if key in trade:ax.axhline(trade[key],color=col,lw=.8,ls='--',label='Baseline '+key)
        if 'entry_time' in trade:
            tx=mdates.date2num(datetime.fromtimestamp(trade['entry_time']/1000,timezone.utc));ax.scatter([tx],[trade['entry']],color='black',marker='^',s=50)
    # Initial axis extent depends ONLY on data and annotations known at the cutoff.
    if not forward:
        ax.set_xlim(mdates.date2num(datetime.fromtimestamp(shown[0]['t']/1000,timezone.utc))-.1,x+.08)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d',tz=timezone.utc));ax.grid(alpha=.17)
    ax.set_ylabel(f'{coin} perpetual price');ax.set_title(f'{coin} — {utc(cutoff)}\n'+('INITIAL: future hidden' if not forward else 'OUTCOME-SELECTED BASELINE ILLUSTRATION, not validation'))
    text='; '.join(f.get('blockers',[])) or 'No recorded blockers'
    fig.text(.07,.02,text[:190],fontsize=9)
    ax.legend(loc='best',fontsize=7,ncol=2);fig.tight_layout(rect=[0,.05,1,1])
    out=root/'charts'/f'{name}.png';out.parent.mkdir(exist_ok=True);fig.savefig(out,dpi=145);plt.close(fig)
    save(out.with_suffix('.json'),dict(coin=coin,cutoff=cutoff,forward_bars=forward,frame=f,
        shown_bars_sha256=hashlib.sha256(json.dumps(shown,sort_keys=True).encode()).hexdigest(),
        selection='Existing BTC/SOL specification cutoffs or fewest blockers then earliest timestamp; baseline examples deliberately outcome-selected.'))
    return str(out)

def context_report(root,decisions):
    archives=read(root/'inputs/archive_evidence.json');macro=[];cot=[]
    def ms(s):return int(datetime.fromisoformat(s).timestamp()*1000) if s else None
    for r in archives:
        m=r.get('macro') or {}
        if m.get('available_at') and m.get('expires_at'):
            macro.append(dict(available_at=ms(m['available_at']),expires_at=ms(m['expires_at']),status=m.get('status'),source=r.get('path')))
        c=r.get('cot') or {};attempts=[a.get('retrieved_at') for a in c.get('provider_attempts',[]) if a.get('retrieved_at')]
        if attempts:cot.append(dict(first_observed=min(attempts),regime=c.get('regime'),report_as_of=[v.get('as_of_date') for v in c.get('markets',{}).values()],release_dates=[v.get('release_date') for v in c.get('markets',{}).values()]))
    joins=[dict(coin=r['coin'],time=r['time'],macro_observation=available_context(macro,r['time'])) for r in decisions if available_context(macro,r['time'])]
    result=dict(archives=len(archives),macro_records=macro,available_macro_decisions=joins,cot_observations=cot,
        policy='First observed metadata is not a historical publication time. COT release_date null remains unavailable before observation. Sparse context not used as an assumed historical pass. Full-context strategy result UNKNOWN.')
    save(root/'context_evidence.json',result);return result

def publish(root):
    ds=read(root/'decisions.json');ledger=read(root/'ledger.json');funnel=read(root/'funnel.json');data=read(root/'inputs/dataset.json');summary=read(root/'summary.json')
    context=context_report(root,ds)
    with (root/'decisions.csv').open('w',newline='') as out:
        names=['coin','time','status','weekly_velocity','weekly_direction','daily_direction','blockers','zone','origin','terminal','targets']
        w=csv.DictWriter(out,fieldnames=names,lineterminator='\n');w.writeheader()
        for r in ds:w.writerow({**{k:r.get(k) for k in names if k in r},'blockers':';'.join(r['blockers']),
            'zone':json.dumps((r['candidate'] or {}).get('zone')),'origin':(r['leg'] or {}).get('origin'),'terminal':(r['leg'] or {}).get('terminal')})
    with (root/'outcomes.csv').open('w',newline='') as out:
        names=['hypothesis','coin','mode','path','status','time','entry_time','end_time','entry','initial_stop','remaining','economics']
        w=csv.DictWriter(out,fieldnames=names,lineterminator='\n');w.writeheader()
        for r in ledger:w.writerow({k:json.dumps(r.get(k)) if isinstance(r.get(k),(dict,list)) else r.get(k) for k in names})
    gate_counts=Counter(b for r in ds for b in r['blockers']);sole=[r for r in ds if r['blockers']==['reaction_absent']]
    distinct={(r['coin'],r['leg']['origin_t'],tuple(r['candidate']['zone'])) for r in sole}
    diagnostics=[]
    for r in sole:
        b=data['assets'][r['coin']]['bars'][r['index']];z=r['candidate']['zone'];d=r['direction']
        body=abs(b['c']-b['o']);wick=min(b['o'],b['c'])-b['l'] if d==1 else b['h']-max(b['o'],b['c'])
        diagnostics.append(dict(coin=r['coin'],time=r['time'],zone=z,origin_time=r['leg']['origin_t'],
            intersects=intersects(b,z),directional_body=d*(b['c']-b['o'])>0,wick_ge_body=wick>=body,
            closes_beyond_midpoint=d*(b['c']-sum(z)/2)>0))
    save(root/'reaction_diagnostic.json',dict(decision_snapshots=len(sole),distinct_coin_origin_zone=len(distinct),
        components_failed=dict(Counter(k for r in diagnostics for k in ('intersects','directional_body','wick_ge_body','closes_beyond_midpoint') if not r[k])),rows=diagnostics,
        meaning='Single-rule eligibility diagnostic, NOT hypothetical winners or independent trades. No outcomes or relaxed replay computed.'))
    review=['# Chart review — frozen primary interpretation','','These initial charts contain no future candles. History was already inspected; they are not genuinely unseen validation. The yellow band is the NEW explicitly assumed BEN construction, not the old six-candle proxy.','']
    for c in data['assets']:
        options=[r for r in ds if r['coin']==c]
        if c in ('BTC','SOL'):
            index=922 if c=='BTC' else 445
            f=next(r for r in options if r['index']==index)
        else:f=min(options,key=lambda r:(len(r['blockers']),r['time']))
        path=chart(root,c,data['assets'][c]['bars'],f,c+'_initial')
        review += [f'## {c}', '',f"Blockers: {', '.join(f['blockers'])}.",'',f'![{c} initial]({path})','']
    # All candidate successes/failures absent if no admission. Never fabricate them.
    old=read(root/'baseline_reproduction/ledger.json');eligible=[r for r in old if r['mode']=='retest' and r['bound']=='pessimistic']
    for label,predicate in [('successful',lambda r:'entry' in r and r['net_20bps_r']>0),('failed',lambda r:'entry' in r and r['net_20bps_r']<0),('untriggered',lambda r:r['status']=='expired')]:
        options=[r for r in eligible if predicate(r)]
        if not options:continue
        r=min(options,key=lambda r:(r['signal_time'],r['coin']));f=dict(time=r['signal_time'],blockers=['LEGACY BASELINE — not a primary-workflow trade'])
        f['candidate']=dict(zone=r['zone'])
        path=chart(root,r['coin'],data['assets'][r['coin']]['bars'],f,'baseline_'+label,forward=60,trade=r)
        review += [f'## Baseline {label} — illustrative, deliberately outcome-selected','',f'![Baseline {label}]({path})','']
    (root/'CHART_REVIEW.md').write_text('\n'.join(review))
    lines=['# Full-strategy research v1: primary branch checkpoint','',
        '**Verdict: INCONCLUSIVE. No production remedy justified.**','',
        f"Replayed {len(ds):,} completed four-hour decisions across six assets. Admitted {sum(r['status']=='admitted' for r in ds)} primary-workflow hypotheses; produced {sum('entry' in r for r in ledger)} policy/path fills.",
        'Do not call zero admissions zero profitability. Net expectancy, economic uncertainty, trade drawdown and mean holding time are unavailable without trades. Price-only hypothetical exposure is zero if there are no admissions; full-context eligibility is UNKNOWN.',
        '', '## What this establishes','',
        '- Theory fidelity improved: locked multi-timeframe premise, explicit zone/reaction and hourly flip replace the old six-candle proxy. However institutional scaling, swing-target confluence and conservative re-entry remain research assumptions—not a certified implementation of the whole theory.',
        '- Executability infrastructure has fixture evidence; no admitted historical primary trades exercise it in this sample. Do not confuse passing unit tests with validated fills or market edge.',
        '- Economic evidence remains the old exploratory baseline. The new interpretation cannot yet be compared economically because it produces no sample. No parameter was relaxed after observing that result.',
        '', '## Admission funnel (snapshots, not independent opportunities)','',
        '| Asset | Decisions | Confirmed impulse | Zone available | Reaction present | Eligible | Sole reaction blocker |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for c,g in funnel.items():
        n=g['decisions'];bc=g['blockers'];lines.append(f"| {c} | {n} | {n-bc.get('impulse_unavailable',0)} | {n-bc.get('zone_unavailable',0)} | {n-bc.get('reaction_absent',0)} | {g['statuses'].get('admitted',0)} | {g['sole_blocker'].get('reaction_absent',0)} |")
    lines+=['',f"Omitting only the reaction blocker would expose {len(sole)} decision snapshots across {len(distinct)} distinct coin/origin/zone combinations. These are NOT {len(sole)} trades. No relaxed PnL test was run.",
        'Reaction-component failures: '+json.dumps(read(root/'reaction_diagnostic.json')['components_failed'])+'. Components overlap.',
        '', '## Reproduced baseline — unchanged known limitations','',
        '| Policy, pessimistic hourly ordering | Fills | Mean net R, 20bps | Mean net R, 40bps |',
        '|---|---:|---:|---:|']
    legacy=read(root/'baseline_reproduction/summary.json')['groups']
    for mode in ('immediate','retest'):
        g=legacy[mode+'/pessimistic/all'];lines.append(f"| {mode} | {g['n']} | {g['net_mean_r']['20']:.5f} | {g['net_mean_r']['40']:.5f} |")
    lines += ['','These numbers reproduce the old results exactly, including documented funding timestamp/count and admission-boundary limitations. They are not corrected new estimates or evidence that the full workflow works.',
        '', '## Coverage and limitations','',
        '- 180-day shared frozen sample, 4,320 hours and 1,080 four-hour candles per asset; exact hourly aggregation. Original six-asset acquisition retained normalized data, not full exchange responses. This provenance gap is disclosed, not repaired by pretending today’s download was the original response.',
        '- Nine complete weekly candles consume the first 392 four-hour decision cutoffs per asset. Missing warmup is unavailable, not a failed momentum prediction.',
        '- Archived macro data are sparse: '+str(len(context['available_macro_decisions']))+' asset-decision joins within recorded availability/expiry. COT snapshots have observation times but incomplete publication metadata. No complete historical context strategy is asserted.',
        '- Present-day instrument metadata is not historical tick/quantity precision. Fee, spread and slippage are explicit scenarios, not measurements. Funding uses entry-notional and timing sensitivity, not historical mark-notional reconstruction.',
        '- Available saved BTC five-minute candles can refine exactly matching hours. Other hours retain two monotone-path sensitivities. Those are NOT exhaustive mathematical bounds over all possible intrabar paths.',
        '- No leveraged account or mark-to-market portfolio is modeled. Closed-trade drawdown would not be account drawdown. No run-frequency profitability claim is made from a setup-visibility check.',
        '- No full economic acceptance test is possible with zero primary trades. Six assets and previously inspected history introduce selection/reuse bias. No prospective collector has been started.',
        '', '## Next action','',
        'Resolve the **daily-impulse versus local-four-hour impulse anchor conflict**, using outcome-hidden daily/4h/hourly overlays and the existing source examples. Audit the overly sparse provisional-terminal confirmation and BEN geometry as interpretation questions—not permission to relax the weekly gate or remove the reaction rule. Freeze a separately versioned contract only if source evidence warrants changing it; do not tune this v1 until it trades.',
        '', '## Reproduction','',
        'Run with `/Users/jhonny/nave/.venv/bin/python research.py capture`, then `verify`, `replay`, `report` from this directory. For charts set `MPLCONFIGDIR=/private/tmp/mpl-cache`. `audit.py` reruns the extended verification suite. All sources and input hashes are local; no network is required for replay.',
        '', '## Artifact guide','',
        '- `CONTRACT.md`, `contract_seal.json`: frozen specification, provenance and timestamp.',
        '- `capture.json`, `inputs/`, `provider_probe*.json`: frozen input provenance and actual API probe responses/errors.',
        '- `decisions.json/.csv`: every decision, all recorded blockers and candidate anchors.',
        '- `ledger.json`, `outcomes.csv`, `summary.json`: complete primary outcome ledger (empty when zero admitted), explicit null performance by asset, period and exclusion.',
        '- `reaction_diagnostic.json`: one-rule eligibility attribution without outcome selection.',
        '- `CHART_REVIEW.md`: six initial primary charts plus legacy success/failure/untriggered illustrations. No invented primary success example.',
        '- `baseline_parity.json`, `test_results.txt`, `verification.json`, `audit.json`: executed verification.',
        '', 'Production, prior experiments, PRs and automation remain unchanged.']
    (root/'REPORT.md').write_text('\n'.join(lines)+'\n')
    save(root/'report_manifest.json',{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*.png'))})
    print('Report and',len(list((root/'charts').glob('*.png'))),'real charts written.')
