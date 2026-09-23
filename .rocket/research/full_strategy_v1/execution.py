"""OHLC path replay, partial quantities, explicit unresolved and funding sensitivity."""
from engine import H,D,inside,flip_step,latest_stop,next_run

def execute_bar(position, bar, path, entry_limit=None):
    """Mutates a private position; no made-up ordering inside a chosen path."""
    p=position; d=p['direction']; events=[];step=bar.get('_step',H)
    vertices=[bar[k] for k in ('o','l','h','c')] if path=='OLHC' else [bar[k] for k in ('o','h','l','c')]
    def enter(price):
        p.update(entry=price,risk=d*(price-p['stop']),remaining=1.,entry_time=bar['t'],
                 entry_time_bounds=[bar['t'],bar['t']+step],exits=[],tp=0)
        events.append('entry')
    def close(price,qty,reason):
        qty=min(qty,p['remaining']);p['remaining']=max(0.,p['remaining']-qty)
        p['exits'].append(dict(price=price,quantity=qty,reason=reason,time=bar['t']+step,
                               time_bounds=[bar['t'],bar['t']+step]))
        events.append(reason)
    def barriers(price,at_open=False):
        if 'entry' not in p or p['remaining']<=1e-12: return
        if d*(price-p['stop'])<=0:
            close(price if at_open else p['stop'],p['remaining'],'stop');return
        while p['tp']<2 and d*(price-p['targets'][p['tp']])>=0:
            n=p['tp'];close(p['targets'][n],.8 if n==0 else .1,'target'+str(n+1));p['tp']+=1
    if 'entry' not in p and entry_limit is not None and d*(vertices[0]-entry_limit)<=0:
        enter(vertices[0])
    barriers(vertices[0],True)
    for a,b in zip(vertices,vertices[1:]):
        if 'entry' not in p and entry_limit is not None and min(a,b)<=entry_limit<=max(a,b):
            enter(entry_limit);a=entry_limit
        if 'entry' not in p or p['remaining']<=1e-12: continue
        # On a monotone segment the order of crossed barriers is deterministic.
        levels=[p['stop']]+p['targets'][p['tp']:]
        for level in sorted(set(x for x in levels if min(a,b)<=x<=max(a,b)),reverse=b<a):
            barriers(level)
        barriers(b)
    return events

def economics(p, funding):
    if 'entry' not in p: return {}
    entry=p['entry'];risk=p['risk'];d=p['direction']
    gross=sum(x['quantity']*d*(x['price']-entry) for x in p['exits'])
    buckets={int(r['time'])//H*H:float(r['fundingRate']) for r in funding}
    start=p['entry_time'];end=p['end_time'];low=high=0.;missing=[]
    for t in range((start+H-1)//H*H,end+1,H):
        if t not in buckets: missing.append(t);continue
        # Boundary fills are only known to their execution hour. Quantity bounds
        # include entry/exit settlement uncertainty and scale partial funding.
        before=sum(x['quantity'] for x in p['exits'] if x['time_bounds'][1]<t)
        through=sum(x['quantity'] for x in p['exits'] if x['time_bounds'][0]<=t)
        qmax=max(0,1-before);qmin=max(0,1-through)
        if t<=p['entry_time_bounds'][1]:qmin=0
        r=d*buckets[t]*entry
        low+=min(r*qmin,r*qmax);high+=max(r*qmin,r*qmax)
    closed=p['remaining']<=1e-12
    result=dict(gross_realized_r=gross/risk,remaining=p['remaining'],funding_missing_hours=missing,
                funding_cost_bounds_r=[low/risk,high/risk],exposure_hours=(end-start)/H,
                completed=closed,net={})
    for bps in (10,20,40):
        cost=entry*bps/10000*(.5+.5*(1-p['remaining']))
        result['net'][str(bps)]=None if missing or not closed else {
            'r_lower':(gross-cost-high)/risk,'r_upper':(gross-cost-low)/risk,
            'notional_lower':(gross-cost-high)/entry,'notional_upper':(gross-cost-low)/entry}
    return result

def simulate(hours, hypothesis, mode, path, funding, invalidations=(),finer=None):
    d=hypothesis['direction'];zone=hypothesis['candidate']['zone'];targets=hypothesis['targets']
    t=hypothesis['time'];expiry=t+8*D
    p=dict(direction=d,stop=hypothesis['passive_stop'],targets=targets,remaining=0.)
    out=dict(time=t,mode=mode,path=path,status='pending',events=[],expiry=expiry,
             origin=hypothesis['leg']['origin'],zone=zone,targets=targets)
    state={};pending_trigger=None;pending_thesis=False
    indexes=[i for i,b in enumerate(hours) if b['t']>=t]
    limit=zone[1 if d==1 else 0]
    for i in indexes:
        b=hours[i];now=b['t'];out['end_time']=now+H
        if 'entry' not in p and now>=expiry:
            out.update(status='expired',end_time=expiry);break
        if 'entry' not in p and (now in invalidations or d*(b['o']-out['origin'])<0):
            out.update(status='invalidated_before_entry',end_time=now);break
        if pending_thesis and 'entry' in p:
            p['exits'].append(dict(price=b['o'],quantity=p['remaining'],reason='thesis_exit',
                                   time=now,time_bounds=[now,now]));p['remaining']=0.
            out.update(status='closed',end_time=now);break
        enter_limit=None
        if 'entry' not in p:
            if mode=='flip' and pending_trigger:
                price=b['o'];p['stop']=pending_trigger['stop']
            elif mode=='passive':
                if not (b['l']<=limit if d==1 else b['h']>=limit): price=None
                else: price=b['o'] if d*(b['o']-limit)<=0 else limit
            else: price=None
            if price is not None:
                risk=d*(price-p['stop'])
                if not inside(price,zone) or risk<=0 or d*(targets[0]-price)<risk:
                    out.update(status='entry_risk_or_zone_rejected');break
                if mode=='flip':
                    p.update(entry=price,risk=risk,remaining=1.,entry_time=now,
                             entry_time_bounds=[now,now],exits=[],tp=0)
                    out['events'].append(dict(time=now,event='entry_next_open'))
                else: enter_limit=limit
        subbars=(finer or {}).get(now,[b])
        if len(subbars)>1:out['finer_hours_used']=out.get('finer_hours_used',0)+1
        for sb in subbars:
            events=execute_bar(p,sb,path,enter_limit)
            for event in events:out['events'].append(dict(time_bounds=[sb['t'],sb['t']+sb.get('_step',H)],event=event))
            if 'entry' in p and p['remaining']<=1e-12:
                out['end_time']=sb['t']+sb.get('_step',H);break
        if 'entry' in p:
            if p['remaining']<=1e-12:out['status']='closed';break
            if p['tp']>=2:
                stop=latest_stop(hours[:i+1],d)
                if stop is not None and d*(stop-p['stop'])>0 and d*(b['c']-stop)>0:p['stop']=stop
            pending_thesis=(now+H in invalidations or
                ((now+H)%(4*H)==0 and d*(b['c']-out['origin'])<0))
        else:
            if (now+H)%(4*H)==0 and d*(b['c']-out['origin'])<0:
                out['status']='invalidated_before_entry';break
            if mode=='flip':
                newer=flip_step(state,hours[:i+1],hypothesis)
                for event in ('swept','broken','trigger'):
                    if event in newer and event not in state:out['events'].append(dict(time=now+H,event=event))
                state=newer
                if state.get('trigger'):pending_trigger=state;out['trigger_time']=state['trigger']
    else:out['status']='unresolved_position' if 'entry' in p else 'unresolved_pending'
    out.setdefault('end_time',t)
    if 'entry' in p:
        out.update(p);out['end_time']=out.get('end_time',t)
        # stop used for initial risk is retained separately from any later trail.
        out['initial_stop']=out['entry']-d*out['risk']
        out['economics']=economics(out,funding)
        deadline=out.get('trigger_time',out['entry_time'])
        out['scheduled_observable']=next_run(t)<=deadline
        out['next_scheduled_run']=next_run(t)
    return out
