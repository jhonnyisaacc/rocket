"""Pure offline candidate mechanics. No provider, account or production imports."""
import math
from collections import defaultdict

H=3600000
D=24*H
W=7*D
MONDAY=4*D

def aggregate(bars, step, cutoff, offset=0):
    groups=defaultdict(list)
    for b in bars:
        start=(b['t']-offset)//step*step+offset
        if b['t']+H<=cutoff and start+step<=cutoff: groups[start].append(b)
    out=[]
    for start, rs in sorted(groups.items()):
        if [b['t'] for b in rs]!=list(range(start,start+step,H)): continue
        out.append(dict(t=start,o=rs[0]['o'],h=max(b['h'] for b in rs),
                        l=min(b['l'] for b in rs),c=rs[-1]['c']))
    return out

def pivots(bars, width, step):
    out=[]
    for i in range(width,len(bars)-width):
        rs=bars[i-width:i+width+1]
        if any(b['t']-a['t']!=step for a,b in zip(rs,rs[1:])): continue
        for side, key in [(1,'h'),(-1,'l')]:
            p=bars[i][key]
            if all(side*(p-b[key])>0 for j,b in enumerate(rs) if j!=width):
                out.append(dict(t=bars[i]['t'],available=bars[i+width]['t']+step,
                                side=side,price=p))
    return out

def velocity(weeks):
    if len(weeks)<9 or any(b['t']-a['t']!=W for a,b in zip(weeks[-9:],weeks[-8:])): return None
    tr=[max(b['h']-b['l'],abs(b['h']-a['c']),abs(b['l']-a['c'])) for a,b in zip(weeks[-9:],weeks[-8:])]
    atr=sum(tr)/8
    return (weeks[-1]['c']-weeks[-5]['c'])/atr if atr else None

def daily_direction(ps):
    highs=[p for p in ps if p['side']==1]; lows=[p for p in ps if p['side']==-1]
    if len(highs)<2 or len(lows)<2: return None
    dh=highs[-1]['price']-highs[-2]['price']; dl=lows[-1]['price']-lows[-2]['price']
    return 1 if dh>0 and dl>0 else -1 if dh<0 and dl<0 else 0

def impulses(daily):
    """As-of daily BOS state; pending terminal confirmation never backdates."""
    ps=pivots(daily,3,D); state=None; states=[]
    for i,b in enumerate(daily):
        avail=[p for p in ps if p['available']<=b['t']]
        events=[]
        for side in (1,-1):
            levels=[p for p in avail if p['side']==side]
            if i and levels and side*(b['c']-levels[-1]['price'])>0 and side*(daily[i-1]['c']-levels[-1]['price'])<=0:
                events.append(side)
        if events:
            direction=events[-1]
            origins=[p for p in avail if p['side']==-direction]
            if origins:
                origin=state['origin'] if state and state['direction']==direction else origins[-1]['price']
                ot=state['origin_t'] if state and state['direction']==direction else origins[-1]['t']
                terminal=b['h' if direction==1 else 'l']
                if not state or state['direction']!=direction or direction*(terminal-state['terminal'])>0:
                    state=dict(direction=direction,origin=origin,origin_t=ot,terminal=terminal,
                               terminal_t=b['t'],bos_time=b['t']+D,confirmed=False)
        if state:
            state=dict(state)
            direction=state['direction']
            if direction*(b['c']-state['origin'])<0: state=None
            elif b['t']>state['terminal_t'] and not state['confirmed']:
                if direction*(b['h' if direction==1 else 'l']-state['terminal'])>0:
                    # A violated provisional terminal waits for a fresh BOS, never rolls.
                    state['terminal_failed']=True
                state['confirmed']=not state.get('terminal_failed',False) and b['t']>=state['terminal_t']+3*D
        states.append(dict(state) if state else None)
    return states

def institutional(swing, origin, direction):
    unit=10**(math.floor(math.log10(origin))-3)
    base=math.floor(swing/(100*unit))
    levels=[(100*k+n)*unit for k in range(base-1,base+2) for n in (0,20,50,80)]
    return max(x for x in levels if x<swing) if direction==1 else min(x for x in levels if x>swing)

def inside(price, zone): return zone[0]<=price<=zone[1]
def intersects(bar, zone): return bar['l']<=zone[1] and bar['h']>=zone[0]

def zone_candidates(h4, daily, weeks, leg, monthly_refs=()):
    d=leg['direction']; origin=leg['origin']; terminal=leg['terminal']
    band=sorted([terminal+(origin-terminal)*r for r in (.75,.86)])
    ps=pivots(h4,2,4*H); out=[]
    refs=list(monthly_refs)
    for rows in (daily,weeks):
        if rows: refs.extend([rows[-1]['o'],rows[-1]['c']])
    for p in reversed(ps):
        if p['side']!=-d or not inside(p['price'],band): continue
        level=institutional(p['price'],origin,d); ben=sorted([p['price'],level])
        zone=[max(ben[0],band[0]),min(ben[1],band[1])]
        if zone[0]>=zone[1]: continue
        factors=['swing','institutional']
        if any(inside(r,ben) for r in refs): factors.append('period_reference')
        if any((d==1 and a['h']<c['l'] and max(a['h'],ben[0])<=min(c['l'],ben[1])) or
               (d==-1 and c['h']<a['l'] and max(c['h'],ben[0])<=min(a['l'],ben[1]))
               for a,c in zip(h4,h4[2:])): factors.append('fvg')
        touches=[q for q in ps if q['t']<p['t'] and q['side']==p['side'] and inside(q['price'],ben)]
        if len(touches)>=2 and touches[-1]['t']-touches[-2]['t']>4*H: factors.append('prior_touches')
        out.append(dict(zone=zone,ben=ben,band=band,pivot=p,factors=factors))
    return out

def reaction(bar, zone, d):
    body=abs(bar['c']-bar['o'])
    wick=min(bar['o'],bar['c'])-bar['l'] if d==1 else bar['h']-max(bar['o'],bar['c'])
    return intersects(bar,zone) and d*(bar['c']-bar['o'])>0 and wick>=body and d*(bar['c']-sum(zone)/2)>0

def objectives(h4,daily,zone,d):
    edge=zone[1 if d==1 else 0]
    prices={p['price'] for p in pivots(h4,2,4*H)+pivots(daily,3,D)
            if p['side']==d and d*(p['price']-edge)>0}
    return sorted(prices,reverse=d==-1)[:2]

def latest_stop(hours,d):
    ps=[p for p in pivots(hours,2,H) if p['side']==-d]
    return ps[-1]['price']*(1-d*.0001) if ps else None

def frame(hours, cutoff):
    hours=[b for b in hours if b['t']+H<=cutoff]
    h4=aggregate(hours,4*H,cutoff); daily=aggregate(hours,D,cutoff); weeks=aggregate(hours,W,cutoff,MONDAY)
    v=velocity(weeks); wd=None if v is None else 1 if v>1.2 else -1 if v< -1.2 else 0
    dd=daily_direction(pivots(daily,3,D)); ls=impulses(daily); leg=ls[-1] if ls else None
    blockers=[]
    if wd is None: blockers.append('weekly_warmup_unknown')
    elif wd==0: blockers.append('weekly_neutral')
    if dd is None: blockers.append('daily_structure_unknown')
    elif dd==0: blockers.append('daily_mixed')
    if wd and dd and wd!=dd: blockers.append('weekly_daily_disagree')
    if not leg or not leg['confirmed']: blockers.append('impulse_unavailable')
    d=leg['direction'] if leg else dd if dd else wd
    if leg and dd and leg['direction']!=dd: blockers.append('impulse_daily_disagree')
    # Full completed calendar-month reference only; no partial month masquerading as closed.
    from datetime import datetime, timezone
    month_groups=defaultdict(list)
    for b in daily:
        dt=datetime.fromtimestamp(b['t']/1000,timezone.utc); month_groups[(dt.year,dt.month)].append(b)
    refs=[]
    import calendar
    for (y,m),bs in sorted(month_groups.items()):
        if len(bs)==calendar.monthrange(y,m)[1]: refs=[bs[0]['o'],bs[-1]['c']]
    zs=zone_candidates(h4,daily,weeks,leg,refs) if leg and leg['confirmed'] else []
    z=zs[0] if zs else None
    if not z: blockers.append('zone_unavailable')
    elif len(z['factors'])<3: blockers.append('confluence_below_three')
    if not z or not h4 or not reaction(h4[-1],z['zone'],d): blockers.append('reaction_absent')
    targets=objectives(h4,daily,z['zone'],d) if z else []
    if len(targets)<2: blockers.append('two_objectives_unavailable')
    stop=latest_stop(hours,d) if d in (1,-1) else None
    if stop is None: blockers.append('hourly_stop_unknown')
    return dict(time=cutoff,weekly_velocity=v,weekly_direction=wd,daily_direction=dd,
                direction=d,leg=leg,candidate=z,targets=targets,passive_stop=stop,
                blockers=blockers,context={'cot':'UNKNOWN','macro':'UNKNOWN','historical_spread':'UNKNOWN'},
                eligible=not blockers)

def flip_step(state, bars, hypothesis):
    """Only call on closed hourly bars after admission. State can never use future pivots."""
    d=hypothesis['direction']; z=hypothesis['candidate']['zone']; b=bars[-1]
    prior=[p for p in pivots(bars[:-1],2,H) if p['available']<=b['t']]
    state=dict(state)
    adverse=[p for p in prior if p['side']==-d]
    opposing=[p for p in prior if p['side']==d and inside(p['price'],z)]
    if state.get('broken'):
        level=state['level']
        if intersects(b,[level,level]) and d*(b['c']-level)>0 and inside(b['c'],z):
            stop=latest_stop(bars,d)
            if stop is not None: return dict(state,trigger=b['t']+H,stop=stop)
    elif state.get('swept') and opposing:
        level=opposing[-1]['price']
        if d*(b['c']-level)>0 and inside(b['c'],z): state.update(broken=b['t']+H,level=level)
    elif adverse:
        p=adverse[-1]['price']
        extreme=b['l' if d==1 else 'h']
        if d*(extreme-p)<0 and d*(b['c']-p)>0 and intersects(b,z): state['swept']=b['t']+H
    return state

def available_context(records, time):
    """Never join report-period dates as if they were release dates."""
    rs=[r for r in records if r.get('available_at') is not None and r['available_at']<=time
        and (r.get('expires_at') is None or time<r['expires_at'])]
    return max(rs,key=lambda r:r['available_at']) if rs else None

def next_run(t):
    base=t//D*D
    return min(x for day in (base,base+D) for hour in (11,17,23) if (x:=day+hour*H)>=t)
