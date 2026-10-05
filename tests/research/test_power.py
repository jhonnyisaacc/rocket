"""Synthetic fixtures only; never load the actual exported population or any market file."""

import ast
import builtins
import copy
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from rocket.research.governance import GateError
from rocket.research.power import (
    ClusterDraws,
    boot_corr,
    boot_mean,
    bootstrap_multiplicity,
    corr,
    interval_probability,
    lower,
    ridge,
    run,
    synthetic_trial,
    validate_geometry,
)


@pytest.fixture
def geometry():
    day = 86_400_000
    origin = int(datetime(2019, 1, 1, tzinfo=UTC).timestamp()*1000)
    rows, ends, groups, next_time = [], {7: -1, 14: -1}, {7: -1, 14: -1}, -1
    for index in range(340):
        cutoff = origin+index*7*day
        decision = cutoff+300_000
        year = datetime.fromtimestamp(decision/1000, UTC).year
        if year > 2025:
            break
        for horizon in (7, 14):
            if decision > ends[horizon]:
                groups[horizon] += 1
            ends[horizon] = max(ends[horizon], cutoff+horizon*day)
        spaced = decision >= next_time
        if spaced:
            next_time = decision+14*day
        rows.append({'id': f'synthetic-{index}', 'cutoff': cutoff, 'decision_time': decision,
                     'year': year, 'fold': year if year in (2023, 2024, 2025) else None,
                     'direction': 1 if index%3 else -1, 'scale': .05,
                     'component_7d': groups[7], 'component_14d': groups[14],
                     'spaced': spaced, 'horizon_supported': True})
    return {'schema': 'rocket.power.geometry.v1', 'rows': rows, 'provenance': {
        'source_revision': '0'*40, 'causal_core_sha256': '0'*64,
        'source_parser_sha256': '0'*64, 'source_files': [], 'real_outcomes_accessed': False,
        'feature_completeness': 'SYNTHETIC_ASSUMPTION', 'coverage_assumption_start': '2020-09-01T00:00:00Z',
        'generator': 'synthetic-only', 'intervals': '[cutoff+5m,cutoff+horizon]'}}


@pytest.mark.parametrize('column', ['y','forward_return_7d','binary_success','mfe','mae','real_forecast','features'])
def test_real_or_unrecognized_columns_rejected(geometry, column):
    geometry['rows'][0][column] = 1
    with pytest.raises(GateError, match='Unknown geometry column'):
        validate_geometry(geometry)


def test_geometry_clocks_membership_and_provenance_rejected(geometry):
    value=copy.deepcopy(geometry); value['provenance']['real_outcomes_accessed']=True
    with pytest.raises(GateError): validate_geometry(value)
    value=copy.deepcopy(geometry); value['rows'][2]['spaced']=not value['rows'][2]['spaced']
    with pytest.raises(GateError, match='Spaced identities'): validate_geometry(value)
    value=copy.deepcopy(geometry); value['rows'][2]['component_14d']+=1
    with pytest.raises(GateError, match='Component geometry'): validate_geometry(value)


def test_simulation_has_no_io_or_outcome_imports(geometry, monkeypatch):
    # Prevent even an attempted file read; fresh synthetic values are the only model inputs.
    def forbidden(*args, **kwargs):
        raise AssertionError('Synthetic simulation attempted file access')
    monkeypatch.setattr(builtins, 'open', forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    monkeypatch.setattr(Path, 'read_text', forbidden)
    first=synthetic_trial(geometry,.2,'clustered',.1,20261005,40)
    assert first==synthetic_trial(geometry,.2,'clustered',.1,20261005,40)


def test_cluster_aggregation_matches_explicit_duplicate_replicates():
    groups=np.array([0,0,1,2,2]); draws=bootstrap_multiplicity(groups,40)
    y=np.array([1.,2.,3.,-1.,4.]); f=np.array([.5,1.,2.,0.,1.]); w=np.array([.2,.2,.2,.2,.2])
    explicit=draws.counts[:,draws.inverse]*w
    expected=np.array([corr(y,f,row/row.sum()) for row in explicit])
    actual=boot_corr(y,f,draws,w)
    np.testing.assert_allclose(np.where(np.isfinite(actual),actual,-np.inf),expected,atol=1e-12)
    selection=np.array([True,False,False,True,False])
    raw=draws.counts[:,draws.inverse]
    with np.errstate(invalid='ignore',divide='ignore'):
        expected_mean=(raw@np.where(selection,y,0))/(raw@selection.astype(float))
    np.testing.assert_allclose(boot_mean(y,selection,draws),expected_mean,equal_nan=True)
    assert isinstance(draws,ClusterDraws)


def test_undefined_bootstrap_draws_never_disappear():
    assert lower(np.array([np.nan]*6+[1.]*94))==-np.inf
    assert lower(np.array([np.nan]*2+[1.]*98))==1
    p=interval_probability(0,2000)
    assert p['probability']==0 and 0 < p['mc_95_interval'][1] < .002


def test_ridge_mean_loss_alpha_and_unpenalized_direction_intercepts():
    x=np.array([[-1.],[1.],[-1.],[1.]])
    direction=np.array([1,1,-1,-1]); y=np.array([1.,3.,-3.,-1.]); w=np.full(4,.25)
    fitted,test=ridge(x,y,direction,w,x,direction,[0])
    # Mean-loss ridge alpha=1 shrinks slope 1 to 1/2; direction intercepts stay +/-2.
    np.testing.assert_allclose(fitted,[1.5,2.5,-2.5,-1.5])
    np.testing.assert_allclose(test,fitted)


def test_power_surface_is_conditional_zero_trial_and_all_gates_reported(geometry):
    result=run(geometry,draws=1,bootstrap_draws=20)
    assert result['conclusion']=='INDETERMINATE_ASSUMPTIONS_REQUIRED'
    assert result['mom002_state']=='NEEDS_PRE_RESULT_GATE_REVIEW'
    assert result['trial_budget']==result['trials_consumed']==0
    assert result['real_outcomes_accessed'] is False
    assert len(result['results'])==5*2*8*3
    assert {v['synthetic_r'] for v in result['results']}=={0,.05,.1,.15,.2,.25,.3,.4}
    assert all('economic_evidence' in v['probabilities'] and 'full_pass' in v['probabilities'] for v in result['results'])


def test_runner_cannot_select_an_outcome_file():
    root=Path(__file__).resolve().parents[2]
    tree=ast.parse((root/'scripts/research/power_audit.py').read_text())
    options=[n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add_argument']
    assert options==['--draws','--bootstrap-draws']
    source=(root/'rocket/research/power.py').read_text()
    tree=ast.parse(source)
    forbidden={'open','read_bytes','read_text','load','score','label','fit_real','urlopen'}
    assert not any(isinstance(n,ast.Call) and ((isinstance(n.func,ast.Name) and n.func.id in forbidden) or (isinstance(n.func,ast.Attribute) and n.func.attr in forbidden)) for n in ast.walk(tree))
