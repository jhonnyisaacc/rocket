"""Review-only independent checks; all fit targets and paths freshly simulated."""
import hashlib,json,math,sys,time
from pathlib import Path
from datetime import UTC,datetime
import numpy as np
import rocket.research.power as power

ROOT=Path(__file__).resolve().parent
geometry=json.loads((ROOT/'research/governance/power/population.geometry.json').read_text())
surface=json.loads((ROOT/'research/governance/power/surface.json').read_text())
checks={}

# Independent structural reconstruction: inclusive-touch intervals and global cooldown.
rows=geometry['rows']; groups={}; cooled=[]; next_time=-1
for days in (7,14):
    end=-1; number=-1; result=[]
    for row in rows:
        if row['decision_time']>end: number+=1
        result.append(number); end=max(end,row['cutoff']+days*86_400_000)
    assert result==[r[f'component_{days}d'] for r in rows]
    groups[days]=result
for row in rows:
    yes=row['decision_time']>=next_time
    assert yes==row['spaced']
    if yes: cooled.append(row); next_time=row['decision_time']+14*86_400_000
checks['geometry']={'candidates':len(rows),'spaced':len(cooled),'components_7d':len(set(groups[7])),'components_14d':len(set(groups[14]))}
coverage=int(datetime.fromisoformat(geometry['provenance']['coverage_assumption_start']).timestamp()*1000)
folds={}
for year in (2023,2024,2025):
    origin=int(datetime(year,1,1,tzinfo=UTC).timestamp()*1000)
    previous=int(datetime(year-1,1,1,tzinfo=UTC).timestamp()*1000)
    valid=[r for r in rows if r['horizon_supported'] and r['decision_time']>=coverage]
    train=[r for r in valid if r['decision_time']<origin-14*86_400_000 and r['cutoff']+7*86_400_000+300000<origin]
    test=[r for r in valid if r['year']==year]
    trailing=[r for r in train if r['spaced'] and r['decision_time']>=previous]
    cap=len(trailing)//4
    folds[year]={'train':len(train),'train_spaced':sum(r['spaced'] for r in train),'test':len(test),'test_spaced':sum(r['spaced'] for r in test),'trailing_train_spaced':len(trailing),'annual_cap':cap,'distinct_spaced_14d_components':len({r['component_14d'] for r in test if r['spaced']})}
    for key in ('train','train_spaced','test','test_spaced','trailing_train_spaced','annual_cap'):
        assert folds[year][key]==surface['geometry']['folds'][str(year)][key]
checks['folds']=folds
checks['annual_maximum_alerts']=sum(v['annual_cap'] for v in folds.values())

# Compare a deliberately heterogeneous 7d-within-14d bootstrap to explicit distinct
# replica IDs and newly recomputed 7d component weights, including duplicate clusters.
g7=np.array([0,0,1,2,2,2,3,4,4]); g14=np.array([0,0,0,1,1,1,1,2,2])
y=np.array([2.,-3.,1.,.5,-1.,5.,-2.,1.,.25]); f=np.array([.2,.6,-.1,.3,.8,.4,-.2,.7,1.]); b=np.array([.4]*9)
selection=np.array([True,False,True,False,False,True,True,True,False]); base=power.weights(g7)
bootstrap_details={}
for definition in (g7,g14):
    mult=power.bootstrap_multiplicity(definition,2000)
    expected_corr=[]; expected_skill=[]; expected_means=[]
    names=np.unique(definition)
    for counts in mult.counts:
        replicate_y=[]; replicate_f=[]; replicate_b=[]; replicate_sel=[]; replica_groups=[]
        replica_id=0
        for group,count in zip(names,counts):
            idx=np.flatnonzero(definition==group)
            for _ in range(int(count)):
                replicate_y.extend(y[idx]); replicate_f.extend(f[idx]); replicate_b.extend(b[idx]); replicate_sel.extend(selection[idx])
                replica_groups.extend((replica_id,int(g7[i])) for i in idx); replica_id+=1
        yy=np.array(replicate_y); ff=np.array(replicate_f); bb=np.array(replicate_b); aa=np.array(replicate_sel)
        counts_by_group={g:replica_groups.count(g) for g in set(replica_groups)}
        ww=np.array([1/counts_by_group[g] for g in replica_groups]); ww/=ww.sum()
        cy=yy-np.dot(ww,yy); cf=ff-np.dot(ww,ff)
        denom=math.sqrt(float(np.dot(ww,cy*cy)*np.dot(ww,cf*cf)))
        expected_corr.append(np.dot(ww,cy*cf)/denom if denom>0 else np.nan)
        expected_skill.append(1-np.dot(ww,(yy-ff)**2)/np.dot(ww,(yy-bb)**2))
        expected_means.append(yy[aa].mean() if aa.any() else np.nan)
    np.testing.assert_allclose(power.boot_corr(y,f,mult,base),expected_corr,equal_nan=True,atol=3e-12)
    np.testing.assert_allclose(power.boot_skill(y,f,b,mult,base),expected_skill,equal_nan=True,atol=3e-12)
    np.testing.assert_allclose(power.boot_mean(y,selection,mult),expected_means,equal_nan=True,atol=3e-12)
    bootstrap_details['7d' if definition is g7 else '14d']={'explicit_duplicate_draws_compared':2000,'correlation_skill_economic_mean_match':True}
checks['bootstrap']=bootstrap_details

# Undefined statistics must remain in the order; exactly 5% passes eligibility
# but its negative-infinity lower tail still fails any positive-lower-bound gate.
undefined=[]
for bad in (0,2,3,5,6):
    v=np.array([np.nan]*bad+[1.]*(100-bad)); result=power.lower(v)
    expected=np.quantile(np.where(np.isfinite(v),v,-np.inf),.025,method='linear') if bad<=2 else -np.inf
    if bad>=3: assert result==-np.inf
    else: assert result==expected
    undefined.append({'undefined_of_100':bad,'lower': '-Infinity' if not np.isfinite(result) else result})
checks['undefined_rule']=undefined
assert power.lower(np.zeros(2000))==0
checks['wilson_0_of_2000']=power.interval_probability(0,2000)

# Alternate ridge solution: eliminate direction intercepts, then fit residualized
# features with alpha=1. Compare 12 fits in every representative synthetic trial.
original_ridge=power.ridge; ridge_calls=0; max_ridge_delta=0.
def alternative_ridge(x,y,d,w,xt,dt,columns):
    global ridge_calls,max_ridge_delta
    actual=original_ridge(x,y,d,w,xt,dt,columns)
    side_mean_y={s:np.average(y[d==s],weights=w[d==s]) for s in (-1,1)}
    if not columns:
        expected=(np.array([side_mean_y[s] for s in d]),np.array([side_mean_y[s] for s in dt]))
    else:
        xx=x[:,columns]; test_x=xt[:,columns]; mu=w@xx; sd=np.sqrt(w@(xx-mu)**2); sd=np.where(sd>0,sd,1)
        z=(xx-mu)/sd; zt=(test_x-mu)/sd
        side_z={s:np.average(z[d==s],weights=w[d==s],axis=0) for s in (-1,1)}
        residual_z=z-np.array([side_z[s] for s in d]); residual_y=y-np.array([side_mean_y[s] for s in d])
        coef=np.linalg.solve(residual_z.T@(w[:,None]*residual_z)+np.eye(len(columns)),residual_z.T@(w*residual_y))
        intercept={s:side_mean_y[s]-side_z[s]@coef for s in (-1,1)}
        expected=(np.array([intercept[s] for s in d])+z@coef,np.array([intercept[s] for s in dt])+zt@coef)
    for aa,ee in zip(actual,expected):
        delta=float(np.max(np.abs(aa-ee))); max_ridge_delta=max(max_ridge_delta,delta)
        np.testing.assert_allclose(aa,ee,rtol=2e-12,atol=2e-12)
    ridge_calls+=1
    return actual
power.ridge=alternative_ridge

def wcorr(y,f,w):
    yy=y-np.dot(w,y); ff=f-np.dot(w,f)
    den=np.sqrt(np.dot(w,yy*yy)*np.dot(w,ff*ff))
    return float(np.dot(w,yy*ff)/den) if den>0 else -math.inf

def wskill(y,f,b,w):
    den=np.dot(w,(y-b)**2)
    return float(1-np.dot(w,(y-f)**2)/den) if den>0 else -math.inf

def explicit_lower(v):
    finite=np.isfinite(v)
    if np.mean(finite)<.95:return -math.inf
    ordered=np.sort(np.where(finite,v,-np.inf)); pos=.025*(len(v)-1); low=math.floor(pos); high=math.ceil(pos)
    if not np.isfinite(ordered[low]) or not np.isfinite(ordered[high]):return -math.inf
    return float(ordered[low]+(ordered[high]-ordered[low])*(pos-low))


structure_details=[]
def independent_structure(c,result):
    # Rebuild every synthetic value from the declared DGP, then independently
    # re-evaluate all causal fit inputs, thresholds, caps, bins and readiness.
    n=len(rows);seed=c['seed'];effect=c['effect'];scenario=c['scenario'];missingness=c['missingness']
    rr=np.random.default_rng(seed)
    ts=np.array([r['decision_time'] for r in rows]);cut=np.array([r['cutoff'] for r in rows]);yr=np.array([r['year'] for r in rows]);side=np.array([r['direction'] for r in rows]);sp=np.array([r['spaced'] for r in rows]);g14=np.array([r['component_14d'] for r in rows])
    available=(ts>=coverage)&np.array([r['horizon_supported'] for r in rows])&(rr.random(n)>=missingness)
    xx=np.sqrt(.75)*rr.normal(size=(n,6))+.5*rr.normal(size=(n,1));beta=np.array([1,-1,1,1,-1,1],float);beta/=np.sqrt(.75*np.sum(beta**2)+.25*np.sum(beta)**2);oracle=xx@beta
    noise=rr.normal(size=n)
    if scenario=='clustered':
        ids=np.array([sorted(set(g14)).index(v) for v in g14]);noise=np.sqrt(.5)*noise+np.sqrt(.5)*rr.normal(size=len(set(g14)))[ids]
    elif scenario=='heavy_tailed': noise=rr.standard_t(3,size=n)/np.sqrt(3)
    strength=np.full(n,effect)
    if scenario in ('up_stronger','down_stronger'):
        strong=1 if scenario=='up_stronger' else -1;factor=np.where(side==strong,1.5,.5);factor/=np.sqrt(np.mean(factor**2));strength*=factor;noise*=np.where(side==strong,.8,1.2)
    yy=strength*oracle+np.sqrt(1-strength**2)*noise
    np.testing.assert_array_equal(available,c['available']);np.testing.assert_allclose(xx,c['x'],atol=0,rtol=0);np.testing.assert_allclose(yy[c['indices']],c['y'],atol=0,rtol=0)
    forecast=np.full((4,n),np.nan);alerts=np.zeros((4,n),bool);bins=np.full(n,-1);ready=True;caps=[]
    for year in (2023,2024,2025):
        origin=int(datetime(year,1,1,tzinfo=UTC).timestamp()*1000);previous=int(datetime(year-1,1,1,tzinfo=UTC).timestamp()*1000)
        train=available&(ts<origin-14*86_400_000)&(cut+7*86_400_000+300000<origin);test=available&(yr==year)
        ti=np.flatnonzero(train);oi=np.flatnonzero(test)
        ready=bool(ready and origin-coverage>=730*86_400_000 and len(ti)>=50 and (train&sp).sum()>=20 and all((train&(side==d)).sum()>=10 for d in (-1,1)) and len(oi)>=20 and len(set(g14[test]))>=5 and all((test&(side==d)).any() for d in (-1,1)))
        groups=[];end=-1;number=-1
        for i in ti:
            if ts[i]>end:number+=1
            groups.append(number);end=max(end,cut[i]+7*86_400_000)
        gg=np.array(groups);_,inverse,counts=np.unique(gg,return_inverse=True,return_counts=True);tw=1/counts[inverse];tw/=tw.sum()
        cap=int(np.count_nonzero(train&sp&(ts>=previous)))//4;caps.append(cap)
        def quantile(values,w,p):
            order=sorted(range(len(values)),key=lambda i:(values[i],i));cum=0
            for i in order:
                cum+=w[i]/sum(w)
                if cum>=p:return values[i]
            return values[order[-1]]
        for model,columns in enumerate(([],[1],[0,1,2],list(range(6)))):
            fitted,predicted=original_ridge(xx[train],yy[train],side[train],tw,xx[test],side[test],columns);forecast[model,test]=predicted
            for shift in (.10,.25):
                shifted_fit,shifted_test=original_ridge(xx[train],yy[train]+shift,side[train],tw,xx[test],side[test],columns)
                np.testing.assert_allclose(shifted_fit,fitted+shift,rtol=2e-12,atol=2e-12);np.testing.assert_allclose(shifted_test,predicted+shift,rtol=2e-12,atol=2e-12)
            candidates=[i for i in oi if sp[i]]
            if model==0: chosen=candidates[3::4][:cap]
            else:
                threshold=quantile(fitted[sp[train]],np.ones(np.count_nonzero(sp[train])),.75);chosen=[i for i in candidates if forecast[model,i]>threshold][:cap]
            alerts[model,chosen]=True
            if model==3:
                cuts=[quantile(fitted,tw,p) for p in (1/3,2/3)]
                bins[test]=[sum(score>boundary for boundary in cuts) for score in predicted]
    oos=available&np.isin(yr,(2023,2024,2025));ready=bool(ready and len(set(g14[oos]))>=15 and np.count_nonzero(oos&sp)>=25)
    np.testing.assert_allclose(forecast,c['forecasts'],equal_nan=True,rtol=0,atol=0);np.testing.assert_array_equal(alerts,c['alerts']);np.testing.assert_array_equal(bins,c['buckets']);assert ready==c['readiness'];assert caps==result['caps']
    structure_details.append({'seed':seed,'DGP_reconstructed':True,'constant_economic_drift_matches_intercept_translation':True,'causal_folds_training_weights_thresholds_caps_bins_readiness_match':True})

captured={}
def trace(frame,event,arg):
    if frame.f_code is power.synthetic_trial.__code__ and event=='return': captured.update(frame.f_locals)
    return trace

def independent_gates(c,result):
    y=c['y']; f=c['f']; b=c['b']; b0=c['b0']; b1=c['b1']; w=c['w']; year=c['year']; g7=c['g7']; g14=c['g14']; bins=c['bins']; a=c['a']; side=c['side']; a_tier=c['a_tier']; a_b0=c['a_b0']; scale=c['scale']
    # Row multiplicities constitute distinct component replicas. The independently
    # validated explicit bootstrap above establishes the multiplicity equivalence.
    corr_lowers=[]; skill_lowers=[]; mono_lowers=[]; mean_lowers={}
    for groups in (g7,g14):
        mult=power.bootstrap_multiplicity(groups,2000); raw=mult.counts[:,mult.inverse]; ww=raw*w; ww/=ww.sum(axis=1)[:,None]
        cy=y-ww@y[:,None] if False else y[None,:]-ww@y[:,None]
        cf=f[None,:]-ww@f[:,None]
        with np.errstate(invalid='ignore',divide='ignore'):
            rc=np.sum(ww*cy*cf,axis=1)/np.sqrt(np.sum(ww*cy**2,axis=1)*np.sum(ww*cf**2,axis=1))
            rs=1-(ww@(y-f)**2)/(ww@(y-b)**2)
            high=(ww@np.where(bins==2,y,0))/(ww@(bins==2).astype(float))
            low=(ww@np.where(bins==0,y,0))/(ww@(bins==0).astype(float))
        corr_lowers.append(explicit_lower(rc));skill_lowers.append(explicit_lower(rs));mono_lowers.append(explicit_lower(high-low))
        for drift in (0.,.10,.25):
            net=scale*(y+drift)-.004
            with np.errstate(invalid='ignore',divide='ignore'):
                means=(raw@np.where(a,net,0))/(raw@a.astype(float))
            mean_lowers.setdefault(drift,[]).append(explicit_lower(means))
    primary=wcorr(y,f,w)>=.1 and all(v>0 for v in corr_lowers)
    increment=wskill(y,f,b,w)>=.05 and wskill(y,f,b0,w)>=.05 and wskill(y,f,b1,w)>=0 and all(v>0 for v in skill_lowers)
    sm=c['spaced'][c['indices']]; sw=np.ones(sm.sum())/sm.sum()
    spaced=bool(sm.any() and wcorr(y[sm],f[sm],sw)>0 and wskill(y[sm],f[sm],b[sm],sw)>=0 and wskill(y[sm],f[sm],b0[sm],sw)>=0)
    fold=all(wcorr(y[year==yr],f[year==yr],power.weights(g7[year==yr]))>0 and wskill(y[year==yr],f[year==yr],b[year==yr],power.weights(g7[year==yr]))>0 for yr in (2023,2024,2025))
    means=[np.average(y[bins==k],weights=w[bins==k]) if (bins==k).any() else None for k in range(3)]
    mono=all(m is not None for m in means) and means[0]<means[1]<means[2] and all(v>0 for v in mono_lowers)
    cardinality=a.sum()>=8 and all((a&(year==yr)).sum()>=2 for yr in (2023,2024,2025)) and all((a&(side==d)).sum()>=2 for d in (-1,1))
    components=np.unique(g14); influences=[abs(np.sum(w[g14==g]*((y[g14==g]-b[g14==g])**2-(y[g14==g]-f[g14==g])**2))) for g in components]
    ranked=sorted(zip(components,influences),key=lambda v:(-v[1],v[0]));removed=[v[0] for v in ranked[:5]]
    masks=[year!=yr for yr in (2023,2024,2025)]+[~np.isin(g14,removed)]
    expected=[]
    for drift in (0.,.1,.25):
        net=scale*(y+drift)-.004
        econ=bool(cardinality and net[a].mean()>0 and a_tier.any() and a_b0.any() and net[a].mean()>net[a_tier].mean() and net[a].mean()>net[a_b0].mean() and all(v>0 for v in mean_lowers[drift]))
        robust=all(mask.any() and wcorr(y[mask],f[mask],power.weights(g7[mask]))>0 and wskill(y[mask],f[mask],b[mask],power.weights(g7[mask]))>0 and (a&mask).any() and net[a&mask].mean()>0 for mask in masks)
        positive=np.where(a,np.maximum(net,0),0);total=positive.sum(); by_year=[positive[year==yr].sum() for yr in (2023,2024,2025)];by_group=[positive[g14==g].sum() for g in components]
        concentration=bool(total>0 and max(by_year)/total<=.5 and max(by_group)/total<=.25 and sum(sorted(by_group)[-5:])/total<=.6)
        adversity=False
        if a.any():
            rr=np.random.default_rng(c['seed']+991); path=np.cumsum(rr.normal(size=(a.sum(),167))/np.sqrt(167),axis=1);fraction=np.arange(1,168)/167
            path=path-path[:,-1,None]*fraction+(y[a]+drift)[:,None]*fraction;mae=np.maximum(0,-np.min(path,axis=1))
            adversity=bool(np.quantile(mae,.5,method='linear')<1 and np.quantile(mae,.9,method='linear')<2)
        # Readiness, thresholds/caps, and synthetic DGP source separately audited.
        gates={'readiness':bool(c['readiness']),'primary_information':bool(primary),'incremental_information':bool(increment),'spaced_consistency':bool(spaced),'fold_consistency':bool(fold),'score_monotonicity':bool(mono),'economic_evidence':bool(econ),'adversity':adversity,'robustness':bool(robust),'concentration':concentration}
        gates['full_pass_without_adversity']=all(v for k,v in gates.items() if k!='adversity');gates['full_pass']=gates['full_pass_without_adversity'] and adversity
        expected.append(gates)
    assert expected==[e['gates'] for e in result['economics']], (expected,result['economics'])

case_results=[]
start=time.perf_counter()
for scenario_index,scenario in enumerate(power.SCENARIOS):
    for effect,missingness,draw in ((0.,0.,0),(.4,0.,7),(.2,.1,21)):
        seed=20261005+scenario_index*1_000_000+draw; captured.clear();sys.settrace(trace)
        try: result=power.synthetic_trial(geometry,effect,scenario,missingness,seed,2000)
        finally:sys.settrace(None)
        assert result is not None
        independent_structure(captured,result)
        independent_gates(captured,result)
        assert result['alerts']<=sum(result['caps'])<=12
        case_results.append({'scenario':scenario,'effect':effect,'missingness':missingness,'seed':seed,'all_12_gates_all_3_drifts_match':True,'alerts':result['alerts'],'caps':result['caps']})
power.ridge=original_ridge
checks['causal_structure_and_DGP_probes']=structure_details;checks['all_gate_recomputations']=case_results;checks['alternate_ridge']={'fit_calls':ridge_calls,'max_absolute_difference':max_ridge_delta};checks['gate_probe_seconds']=time.perf_counter()-start

# The five largest of K positive components must sum to at least 5/K.
# Equal-positive examples demonstrate K=8 impossible and K=9 possible.
checks['concentration_bound']={}
for k in (8,9,12):
    values=np.ones(k);share=float(np.sort(values)[-5:].sum()/values.sum());assert share+1e-14>=min(1,5/k)
    checks['concentration_bound'][str(k)]={'equal_positive_top_5_share':share,'can_satisfy_60pct':bool(share<=.6)}
assert not checks['concentration_bound']['8']['can_satisfy_60pct'] and checks['concentration_bound']['9']['can_satisfy_60pct']

# Surface self-consistency and full conjunction are observable from marginal counts:
# full <= every required gate, upper-bound full <= all non-adversity gates.
assert len(surface['results'])==240
keys=set()
for v in surface['results']:
    key=(v['scenario'],v['missingness'],v['synthetic_r'],v['economic_drift_S']);assert key not in keys;keys.add(key)
    for gate,prob in v['probabilities'].items():
        assert prob==power.interval_probability(prob['passed'],2000)
    full=v['probabilities']['full_pass']['passed'];upper=v['probabilities']['full_pass_without_adversity']['passed']
    assert full<=upper
    for gate in power.GATES[:10]: assert full<=v['probabilities'][gate]['passed']
    for gate in power.GATES[:10]:
        if gate!='adversity': assert upper<=v['probabilities'][gate]['passed']
checks['surface']={'rows':240,'all_probability_counts_and_wilson_intervals_match':True,'all_full_conjunction_inequalities_match':True,'all_full_pass_counts_zero':all(v['probabilities']['full_pass']['passed']==0 for v in surface['results']),'all_without_adversity_counts_zero':all(v['probabilities']['full_pass_without_adversity']['passed']==0 for v in surface['results'])}
checks['zero_oracle_signal_marginal_maxima']={gate:max(v['probabilities'][gate]['probability'] for v in surface['results'] if v['synthetic_r']==0) for gate in power.GATES}
(ROOT/'independent_probe_results.json').write_text(json.dumps(checks,indent=2,allow_nan=False)+'\n')
print(json.dumps(checks,indent=2,allow_nan=False))
