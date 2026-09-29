import copy
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rocket.cli import app
from rocket.research import governance as g


@pytest.fixture
def inputs():
    state = g.read(g.DEFAULT_STATE)
    checkpoint = g.read(g.ROOT / "docs/research/memecoin/experiments/ER-001-CHECKPOINT.json")
    # Use a deliberate pre-admission scenario, independent of live research progress.
    state["active_experiment"] = None
    state["admissions"] = {}
    family = state["families"][checkpoint["hypothesis_family"]]
    family.update(status="OPEN", continuation_budget=1, operator_review_required=False)
    return state, checkpoint


def approval(state, checkpoint):
    return {
        "schema": "rocket.workflow-review.v1",
        "packet_sha256": g.digest(g.packet(state, checkpoint)),
        "reviewer": "independent-human",
        "decision": "WORKFLOW_OK",
        "checks": dict.fromkeys(g.CHECKS, True),
        "reasons": [],
    }


def test_allowed_different_registered_family(inputs):
    state, cp = inputs
    assert state["families"]["generic_early_launch_signals"]["status"] == "REJECTED"
    assert g.review(state, cp, approval(state, cp))["decision"] == "WORKFLOW_OK"


@pytest.mark.parametrize("status", ["REJECTED", "REVIEW_REQUIRED"])
def test_stopped_family_and_operator_review(inputs, status):
    state, cp = inputs
    family = state["families"][cp["hypothesis_family"]]
    family.update(status=status, operator_review_required=True)
    verdict = g.review(state, cp, approval(state, cp))
    assert verdict["decision"] == "WORKFLOW_BLOCK"
    assert "OPERATOR_REVIEW_REQUIRED" in verdict["reasons"]


def test_explicit_reopening_is_scoped(inputs):
    state, cp = inputs
    family = state["families"][cp["hypothesis_family"]]
    family.update(
        status="REJECTED",
        operator_review_required=True,
        reopening={
            "condition": "invalid_prior_test",
            "experiment": cp["experiment"],
            "evidence": "reviewed decoder bug",
            "operator_authorization": "human decision 123",
        },
    )
    assert g.review(state, cp, approval(state, cp))["decision"] == "WORKFLOW_OK"
    family["reopening"]["experiment"] = "ER-002"
    assert g.review(state, cp, approval(state, cp))["decision"] == "WORKFLOW_BLOCK"


@pytest.mark.parametrize("mutation", ["stale", "self", "false_check", "block", "missing"])
def test_independent_review_binding(inputs, mutation):
    state, cp = inputs
    review = approval(state, cp)
    if mutation == "stale":
        cp["new_information"] += " changed"
    elif mutation == "self":
        review["reviewer"] = cp["proposer"]
    elif mutation == "false_check":
        review["checks"]["decision_value"] = False
    elif mutation == "block":
        review["decision"] = "WORKFLOW_BLOCK"
    else:
        review = None
    assert g.review(state, cp, review)["decision"] == "WORKFLOW_BLOCK"


@pytest.mark.parametrize(
    "key,value",
    [
        ("can_change_decision", "true"),
        ("hypothesis_family", "new-name"),
        ("previous_result", "stale"),
        ("economic_gate_status", "PASSED"),
    ],
)
def test_fail_closed_checkpoint(inputs, key, value):
    state, cp = inputs
    cp[key] = value
    with pytest.raises(ValueError):
        g.review(state, cp)


def test_category_budget_and_no_value_block(inputs):
    state, cp = inputs
    family = state["families"][cp["hypothesis_family"]]
    family["continuation_budget"] = 0
    cp.update(
        category="infrastructure_calibration",
        work_kind="infrastructure_calibration",
        can_change_decision=False,
    )
    reasons = g.review(state, cp, approval(state, cp))["reasons"]
    assert {
        "CONTINUATION_BUDGET_EXHAUSTED",
        "CATEGORY_FORBIDDEN",
        "NO_STRATEGY_DECISION_VALUE",
        "INFRASTRUCTURE_WITHOUT_ALPHA_DEPENDENCY",
    } <= set(reasons)


def test_start_consumes_budget_result_suspends_and_no_double_count(inputs, tmp_path):
    state, cp = inputs
    path = tmp_path / "state.json"
    g.save(path, state)
    assert g.start(path, cp, approval(state, cp))["decision"] == "WORKFLOW_OK"
    saved = g.read(path)
    assert saved["families"][cp["hypothesis_family"]]["continuation_budget"] == 0
    assert g.start(path, cp, approval(state, cp))["decision"] == "WORKFLOW_BLOCK"
    result = {
        "schema": "rocket.direction-result.v1",
        "experiment": cp["experiment"],
        "economic_test": True,
        "cohort": "cohort-1",
        "outcome": "NEGATIVE",
        "evidence": "docs/research/memecoin/WORKFLOW_AUDIT.md",
    }
    g.record_result(path, result)
    saved = g.read(path)
    family = saved["families"][cp["hypothesis_family"]]
    assert family["independent_economic_failures"] == 1
    assert family["status"] == "REVIEW_REQUIRED"
    assert saved["active_experiment"] is None
    # Separate test using same cohort: retained but not independent evidence.
    saved["active_experiment"] = "ER-002"
    saved["admissions"]["ER-002"] = copy.deepcopy(saved["admissions"]["ER-001"])
    g.save(path, saved)
    g.record_result(path, dict(result, experiment="ER-002"))
    assert g.read(path)["families"][cp["hypothesis_family"]]["independent_economic_failures"] == 1


def test_calibration_cannot_reset_failure(inputs, tmp_path):
    state, cp = inputs
    family = state["families"][cp["hypothesis_family"]]
    family["economic_evidence"] = [{"cohort": "prior", "outcome": "NEGATIVE"}]
    path = tmp_path / "state.json"
    g.save(path, state)
    g.start(path, cp, approval(state, cp))
    result = {
        "schema": "rocket.direction-result.v1",
        "experiment": cp["experiment"],
        "economic_test": False,
        "outcome": "CANDIDATE",
        "evidence": "docs/research/memecoin/WORKFLOW_AUDIT.md",
    }
    with pytest.raises(ValueError):
        g.record_result(path, result)
    result["outcome"] = "CALIBRATION"
    g.record_result(path, result)
    family = g.read(path)["families"][cp["hypothesis_family"]]
    assert family["independent_economic_failures"] == 1
    assert family["operator_review_required"] is True


def test_prospective_guard_blocks_before_network(inputs, monkeypatch, tmp_path):
    state, cp = inputs
    path = tmp_path / "state.json"
    g.save(path, state)
    monkeypatch.setattr(g, "DEFAULT_STATE", path)
    monkeypatch.delenv("ROCKET_RESEARCH_EXPERIMENT", raising=False)
    with pytest.raises(SystemExit, match="WORKFLOW_BLOCK"):
        g.require_prospective_admission()
    # Retrospective admission cannot authorize a prospective collector.
    g.start(path, cp, approval(state, cp))
    monkeypatch.setenv("ROCKET_RESEARCH_EXPERIMENT", cp["experiment"])
    with pytest.raises(SystemExit, match="WORKFLOW_BLOCK"):
        g.require_prospective_admission()


def test_prospective_guard_valid_and_stale(inputs, monkeypatch, tmp_path):
    state, cp = inputs
    family = state["families"][cp["hypothesis_family"]]
    family["allowed_categories"] = ["prospective_alpha"]
    family["forbidden_categories"] = []
    cp["category"] = "prospective_alpha"
    path = tmp_path / "state.json"
    g.save(path, state)
    g.start(path, cp, approval(state, cp))
    monkeypatch.setattr(g, "DEFAULT_STATE", path)
    monkeypatch.setenv("ROCKET_RESEARCH_EXPERIMENT", cp["experiment"])
    g.require_prospective_admission()
    saved = g.read(path)
    saved["objective"] += " changed"
    g.save(path, saved)
    with pytest.raises(SystemExit, match="stale"):
        g.require_prospective_admission()


def test_cli_blocks_missing_review_exports_packet(inputs, tmp_path):
    _, cp = inputs
    checkpoint = tmp_path / "checkpoint.json"
    g.save(checkpoint, cp)
    packet = tmp_path / "packet.json"
    result = CliRunner().invoke(
        app, ["research", "review", "--checkpoint", str(checkpoint), "--packet-out", str(packet)]
    )
    assert result.exit_code == 2
    assert json.loads(result.stdout)["decision"] == "WORKFLOW_BLOCK"
    assert g.read(packet)["schema"] == "rocket.workflow-packet.v1"


def test_cli_start_invalid_json_is_block(tmp_path):
    malformed = tmp_path / "bad.json"
    malformed.write_text("[]")
    result = CliRunner().invoke(
        app,
        [
            "research",
            "start",
            "ER-001",
            "--checkpoint",
            str(malformed),
            "--independent-review",
            str(malformed),
        ],
    )
    assert result.exit_code == 2
    assert json.loads(result.stdout)["reasons"] == ["INVALID_GOVERNANCE_INPUT"]


def test_capture_entrypoints_have_guard():
    files = [
        "memecoin_capture_py.py",
        "memecoin_block_capture.py",
        "memecoin_pumpportal_capture.py",
        "memecoin_curve_snapshot_capture.py",
        "memecoin_live_actor_capture.py",
        "memecoin_route_snapshot_capture.py",
        "memecoin_pump_buy_companion.py",
        "memecoin_pump_buy_stratified.py",
    ]
    for file in files:
        text = (Path("scripts/research") / file).read_text()
        assert "    require_prospective_admission()" in text


def test_actual_generic_family_blocked(inputs):
    state, cp = inputs
    cp.update(
        hypothesis_family="generic_early_launch_signals",
        experiment="MC-024",
        previous_result="MC-022",
        economic_gate_status="FAILED_COSTED_PROXY",
        category="infrastructure_calibration",
        work_kind="infrastructure_calibration",
        alpha_dependency="unvalidated flow",
    )
    verdict = g.review(state, cp, approval(state, cp))
    assert {
        "FAMILY_STOPPED",
        "OPERATOR_REVIEW_REQUIRED",
        "CATEGORY_FORBIDDEN",
        "CONTINUATION_BUDGET_EXHAUSTED",
    } <= set(verdict["reasons"])


def test_conflicting_category_deny_wins(inputs):
    state, cp = inputs
    state["families"][cp["hypothesis_family"]]["forbidden_categories"].append(cp["category"])
    assert "CATEGORY_FORBIDDEN" in g.review(state, cp, approval(state, cp))["reasons"]


def test_blocked_start_does_not_write(inputs, tmp_path):
    state, cp = inputs
    path = tmp_path / "state.json"
    g.save(path, state)
    before = path.read_bytes()
    verdict = g.start(path, cp, dict(approval(state, cp), decision="WORKFLOW_BLOCK"))
    assert verdict["decision"] == "WORKFLOW_BLOCK"
    assert path.read_bytes() == before
    assert not path.with_suffix(".json.lock").exists()


def test_result_missing_evidence_does_not_resolve(inputs, tmp_path):
    state, cp = inputs
    path = tmp_path / "state.json"
    g.save(path, state)
    g.start(path, cp, approval(state, cp))
    before = path.read_bytes()
    with pytest.raises(OSError):
        g.record_result(
            path,
            {
                "schema": "rocket.direction-result.v1",
                "experiment": "ER-001",
                "economic_test": True,
                "cohort": "new",
                "outcome": "NEGATIVE",
                "evidence": "docs/research/does-not-exist.md",
            },
        )
    assert path.read_bytes() == before


def test_node_entrypoints_block_without_sdk_or_network():
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    for filename in [
        "memecoin_capture.mjs",
        "memecoin_pump_unsigned_buy.cjs",
        "memecoin_amm_unsigned_simulation.cjs",
    ]:
        result = subprocess.run(
            [node, str(g.ROOT / "scripts/research" / filename)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 2
        assert "WORKFLOW_BLOCK" in result.stderr


def test_internal_steps_reuse_budget_and_reject_suspension(inputs, tmp_path):
    state, cp = inputs
    path = tmp_path / "state.json"
    g.save(path, state)
    g.start(path, cp, approval(state, cp))
    before = path.read_bytes()
    for step in cp["allowed_steps"]:
        verdict = g.require_experiment_step(cp["experiment"], step, path)
        assert verdict["decision"] == "WORKFLOW_OK"
        assert verdict["budget_consumed"] is False
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="outside approved"):
        g.require_experiment_step(cp["experiment"], "production", path)
    saved = g.read(path)
    saved["admissions"][cp["experiment"]]["status"] = "SUSPENDED"
    g.save(path, saved)
    with pytest.raises(ValueError, match="no active admission"):
        g.require_experiment_step(cp["experiment"], "dataset_acquisition", path)


def test_internal_step_stale_binding_blocks(inputs, tmp_path):
    state, cp = inputs
    path = tmp_path / "state.json"
    g.save(path, state)
    g.start(path, cp, approval(state, cp))
    saved = g.read(path)
    saved["objective"] += " changed"
    g.save(path, saved)
    with pytest.raises(ValueError, match="stale"):
        g.require_experiment_step(cp["experiment"], "dataset_acquisition", path)
