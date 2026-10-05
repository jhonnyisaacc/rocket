"""Repository dispatch authority and pre-result controls; no outcome scoring."""

import copy
import json
from pathlib import Path

import pytest

from rocket.research.governance import GateError, next_item, verify_manifest
from rocket.research.policy import authority, mom002_prerequisites, pr_action

ROOT=Path(__file__).resolve().parents[2]


def snapshot_for(key):
    config=authority(ROOT); contract=config['items'][key]; fields=contract['fields']
    selected={
        'id':contract['id'],'project_id':config['project']['id'],'repository':'jhonnyisaacc/rocket',
        'primary_work_item':True,'status':'Ready','priority':fields['Priority'],
        'admission_verified':True,'unlock_verified':True,'dependencies_verified':True,
        'kill_condition':fields['Kill Condition'],'research_state':'Admitted',
        'review_tier':fields['Review Tier'],'gate_source':fields['Gate Source'],
        'trial_budget':fields['Trial Budget'],'trials_consumed':fields['Trials Consumed']}
    others=[{'id':config['items'][other]['id'],'project_id':config['project']['id'],
             'repository':'jhonnyisaacc/rocket','primary_work_item':True,'status':'Parked'}
            for other in config['primary_work_item_keys'] if other!=key]
    return {'project_id':config['project']['id'],'items':[selected,*others]}


def test_maintenance_does_not_need_isolated_scientific_review():
    snapshot=snapshot_for('cftc')
    assert next_item(snapshot)==snapshot['items'][0]
    assert 'isolated_review_package_verified' not in snapshot['items'][0]


def test_unrelated_issue_pr_or_fake_primary_cannot_dispatch():
    snapshot=snapshot_for('cftc')
    for change in ({'id':'unrelated-issue'}, {'repository':'someone/else'}, {'project_id':'other-project'}, {'id':authority(ROOT)['items']['pr49']['id']}):
        value=copy.deepcopy(snapshot);value['items'][0].update(change)
        with pytest.raises(GateError):next_item(value)
    value=copy.deepcopy(snapshot);value['items'][0]['primary_work_item']=False
    assert next_item(value) is None
    snapshot['project_id']='other-project'
    with pytest.raises(GateError,match='canonical Project'):next_item(snapshot)


def test_historical_or_operational_rows_never_compete_for_wip():
    snapshot=snapshot_for('power')
    historical=snapshot_for('cftc')['items'][0];historical.update(status='In Progress',research_state='Historical')
    snapshot['items']=[item for item in snapshot['items'] if item['id']!=historical['id']]
    snapshot['items'].extend([dict(historical),dict(historical,id='old-pr'),dict(historical,id='operational-service')])
    assert next_item(snapshot)['id']==snapshot['items'][0]['id']


def test_ordinary_engineering_prs_are_outside_research_dispatch_and_wip():
    snapshot = snapshot_for('power')
    snapshot['items'].extend({
        'id': f'ordinary-pr-{number}', 'status': 'In Progress',
        'primary_work_item': True, 'repository': 'jhonnyisaacc/rocket',
        'project_id': snapshot['project_id'],
    } for number in (63, 64, 999))
    assert next_item(snapshot) == snapshot['items'][0]
    config = authority(ROOT)
    assert config['repository_workflow']['mode'] == 'LIGHTWEIGHT'
    assert config['repository_workflow']['required_github_review'] is False
    assert config['repository_workflow']['required_governance_check'] is False
    assert config['repository_workflow']['separate_github_identity_required'] is False
    assert 'identities' not in config['primary_work_item_keys']
    assert 'independent_github_review' not in pr_action(config, 57)['missing_blockers']


def test_incomplete_inventory_or_duplicate_rows_cannot_evade_wip():
    snapshot=snapshot_for('power')
    snapshot['items'].pop()
    with pytest.raises(GateError,match='Complete canonical primary inventory'):next_item(snapshot)
    snapshot=snapshot_for('power');snapshot['items'].append(snapshot['items'][0])
    with pytest.raises(GateError,match='Duplicate primary WIP'):next_item(snapshot)


def test_human_and_capital_items_not_dispatched():
    assert next_item(snapshot_for('charter')) is None
    assert next_item(snapshot_for('risk_charter')) is None


def test_project_edit_cannot_change_review_or_trial_policy():
    snapshot=snapshot_for('power');snapshot['items'][0]['review_tier']='MAINTENANCE'
    with pytest.raises(GateError,match='cannot override'):next_item(snapshot)
    config=authority(ROOT)
    assert config['items']['mom002']['fields']['Trial Budget']==1
    assert config['items']['mom002']['fields']['Trials Consumed']==0
    assert config['items']['power']['fields']['Trial Budget']==0


def test_wrong_or_spent_experiment_cannot_be_dispatched(tmp_path, monkeypatch):
    from rocket.research import policy
    from rocket.research.governance import canonical, digest

    snapshot=snapshot_for('mom002');item=snapshot['items'][0]
    item.update(isolated_review_package_verified=True,experiment_id='SYN-OTHER')
    monkeypatch.setattr(policy,'mom002_prerequisites',lambda *args: {})
    with pytest.raises(GateError,match='substitute another experiment'):next_item(snapshot)
    folder=tmp_path/'research/governance';folder.mkdir(parents=True)
    (folder/'project.json').write_text(json.dumps(authority(ROOT)))
    synthetic={'experiment_id':'MOM-002','trial_consumed':True,'phase':'START','previous_sha256':None}
    synthetic['record_sha256']=digest(canonical(synthetic))
    (folder/'invocations.jsonl').write_bytes(canonical(synthetic)+b'\n')
    item['experiment_id']='MOM-002'
    assert next_item(snapshot,root=tmp_path) is None


def test_mom002_freeze_and_review_require_power_dependency(tmp_path):
    folder=tmp_path/'research/governance';folder.mkdir(parents=True)
    value=json.loads((ROOT/'research/governance/mom002_prerequisites.json').read_text())
    value['requirements']['power_audit']['status']='PENDING'
    # Isolate the missing power acceptance after making other acceptance records synthetic.
    for name,record in value['requirements'].items():
        if name=='power_audit':continue
        record.update(status='ACCEPTED',reviewer='synthetic-independent',evidence='synthetic',timestamp='2026-01-01T00:00:00Z',reviewed_revision='0'*40,artifacts=[{'path':'synthetic.txt','sha256':'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}],human_decision_recorded=True)
    (tmp_path/'synthetic.txt').write_bytes(b'')
    (folder/'mom002_prerequisites.json').write_text(json.dumps(value))
    with pytest.raises(GateError,match='power_audit'):mom002_prerequisites(tmp_path)
    with pytest.raises(GateError,match='power_audit'):
        verify_manifest(tmp_path,{'schema':'rocket.research.manifest.v1','experiment_id':'MOM-002','state':'FROZEN','safety_boundary':'READ_ONLY_RESEARCH_ONLY_HUMAN_GATED'})
    with pytest.raises(GateError,match='prerequisite not accepted'):next_item(snapshot_for('review'))


def test_exact_pr_dispositions_and_preservation_blockers():
    config=authority(ROOT)
    expected={26:'CLOSE_EVIDENCE_ARCHIVE',38:'CLOSE_EVIDENCE_ARCHIVE',40:'CLOSE_EVIDENCE_ARCHIVE',46:'CLOSE_EVIDENCE_ARCHIVE',49:'MERGE_WHEN_ACCEPTED',50:'CLOSE_EVIDENCE_ARCHIVE',57:'MERGE_WHEN_ACCEPTED'}
    assert {int(n):v['disposition'] for n,v in config['pr_dispositions'].items()}==expected
    for n in expected:
        plan=pr_action(config,n)
        assert plan['action']=='KEEP_OPEN' and plan['research_admitted'] is False
        assert plan['missing_blockers'] and plan['agent_merge_authorized'] is False
    assert 'reconciliation_accepted' in pr_action(config,50)['missing_blockers']
    assert 'governance_merged' in pr_action(config,49)['missing_blockers']
    record=config['pr_dispositions']['50']
    plan=pr_action(config,50,[b['id'] for b in record['blockers']])
    assert plan['action']=='READY_FOR_DOCUMENTED_EVIDENCE_CLOSURE'


def test_required_project_field_types_and_options():
    config=authority(ROOT);fields={v['name']:v for v in config['fields']}
    assert fields['Trial Budget']['dataType']=='NUMBER'
    assert fields['Trial Budget']['id']!=fields['Trials Consumed']['id']
    assert {v['name'] for v in fields['Review Tier']['options']}=={'MAINTENANCE','FOUNDATION','SCIENTIFIC_ADMISSION','PROSPECTIVE_VALIDATION','CAPITAL'}
    assert {v['name'] for v in fields['Gate Source']['options']}=={'CODE','HUMAN','DATA','REVIEW','NONE'}
