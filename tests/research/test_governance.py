"""Adversarial governance checks using synthetic files only; no market experiment."""

import subprocess
import sys
from pathlib import Path

import pytest

from rocket.research.governance import (
    BOUNDARY,
    GOVERNANCE,
    JOURNAL,
    GateError,
    canonical,
    digest,
    disposition,
    git,
    next_item,
    read_chain,
    score,
    verify_manifest,
    verify_repository,
)


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD").decode().strip()


@pytest.fixture
def synthetic_repo(tmp_path):
    root = tmp_path
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    git(root, "config", "user.name", "Synthetic test")
    git(root, "config", "user.email", "synthetic@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "config", "core.hooksPath", "/dev/null")
    (root / GOVERNANCE / "manifests").mkdir(parents=True)
    (root / JOURNAL).write_bytes(b"")
    (root / GOVERNANCE / "invalidations.jsonl").write_bytes(b"")
    (root / "docs/research").mkdir(parents=True)
    (root / "docs/research/TRIAL_LEDGER.md").write_text("Inherited trials: preserve me\n")
    artifacts = {}
    for role in ("contract", "population", "features", "model", "runtime"):
        p = root / (role + ".txt")
        p.write_text("Synthetic artifact: " + role)
        artifacts[role] = [{"path": p.name, "sha256": digest(p.read_bytes())}]
    scorer = root / "scorer.py"
    scorer.write_text("import json\nprint(json.dumps({'experiment_id': 'SYN-001', 'result': 'FAIL'}))\n")
    artifacts["gate"] = [{"path": scorer.name, "sha256": digest(scorer.read_bytes())}]
    dataset = root / "synthetic.json"
    dataset.write_text('{"synthetic": true}')
    freeze = commit(root, "Synthetic pre-result artifacts")
    manifest = {
        "schema": "rocket.research.manifest.v1", "experiment_id": "SYN-001",
        "family": "Synthetic", "state": "ADMITTED", "safety_boundary": BOUNDARY,
        "freeze_revision": freeze, "artifacts": artifacts, "trial_budget": 1,
        "trial_number": 1, "scoring_authorized": True, "proposer": "designer",
        "implementer": "builder", "dataset": {"path": dataset.name, "sha256": digest(dataset.read_bytes())},
        "scorer": {"path": "scorer.py", "protocol": "python-json-v1", "timeout_seconds": 10,
                   "python_version": sys.version},
        "approval": {"reviewer": "independent", "decision": "APPROVE", "reviewed_revision": freeze,
                     "artifact_fingerprint": digest(canonical(artifacts)), "timestamp": "2026-01-01T00:00:00Z",
                     "evidence": "Synthetic independent approval"},
    }
    path = root / GOVERNANCE / "manifests/SYN-001.json"
    path.write_bytes(canonical(manifest))
    admitted = commit(root, "Synthetic reviewed admission")
    git(root, "update-ref", "refs/remotes/origin/main", admitted)
    return root, manifest, admitted


@pytest.mark.parametrize("role", ["contract", "population", "features", "model", "gate", "runtime"])
def test_each_frozen_role_rejects_tampering(synthetic_repo, role):
    root, manifest, _ = synthetic_repo
    verify_manifest(root, manifest)
    (root / manifest["artifacts"][role][0]["path"]).write_text("tampered")
    with pytest.raises(GateError, match="Frozen artifact changed"):
        verify_manifest(root, manifest)


def test_editing_hash_and_manifest_cannot_rewrite_base_freeze(synthetic_repo):
    root, manifest, base = synthetic_repo
    (root / "contract.txt").write_text("Amended after freeze")
    manifest["artifacts"]["contract"][0]["sha256"] = digest((root / "contract.txt").read_bytes())
    manifest["freeze_revision"] = commit(root, "Attempt to re-register same trial")
    manifest["approval"]["reviewed_revision"] = manifest["freeze_revision"]
    manifest["approval"]["artifact_fingerprint"] = digest(canonical(manifest["artifacts"]))
    (root / GOVERNANCE / "manifests/SYN-001.json").write_bytes(canonical(manifest))
    with pytest.raises(GateError, match="Frozen manifest changed/deleted"):
        verify_repository(root, base)


def test_deleting_registry_does_not_evade_freeze(synthetic_repo):
    root, _, base = synthetic_repo
    (root / GOVERNANCE / "manifests/SYN-001.json").unlink()
    with pytest.raises(GateError, match="Frozen manifest changed/deleted"):
        verify_repository(root, base)


@pytest.mark.parametrize("reviewer", ["designer", "builder", None])
def test_self_approval_rejected(synthetic_repo, reviewer):
    root, manifest, _ = synthetic_repo
    manifest["approval"]["reviewer"] = reviewer
    with pytest.raises(GateError, match="Independent reviewer"):
        verify_manifest(root, manifest)


def test_official_fail_receipt_and_retry_are_durable(synthetic_repo):
    root, _, _ = synthetic_repo
    result = score(root, "SYN-001")
    assert result["result"] == "FAIL"
    assert result["trial_consumed"]
    records = read_chain((root / JOURNAL).read_bytes())
    assert [r["phase"] for r in records] == ["START", "FINISH"]
    assert all(r["dataset_fingerprint"] and r["frozen_hashes"] for r in records)
    assert result["commit_sha"] and result["result_fingerprint"]
    new_head = commit(root, "Publish synthetic invocation receipt")
    git(root, "update-ref", "refs/remotes/origin/main", new_head)
    retry = score(root, "SYN-001")
    assert retry["result"] == "BLOCKED" and not retry["trial_consumed"]
    assert "Trial already started" in retry["reason"]
    assert len(read_chain((root / JOURNAL).read_bytes())) == 3


def test_draft_and_wrong_data_never_run_scorer(synthetic_repo):
    root, manifest, _ = synthetic_repo
    (root / "synthetic.json").write_text("wrong bytes")
    head = commit(root, "Different dataset")
    git(root, "update-ref", "refs/remotes/origin/main", head)
    result = score(root, "SYN-001")
    assert result["result"] == "BLOCKED" and not result["trial_consumed"]
    assert "Dataset differs" in result["reason"]
    assert len(read_chain((root / JOURNAL).read_bytes())) == 1
    manifest.update(state="DRAFT", scoring_authorized=False)
    (root / GOVERNANCE / "manifests/SYN-001.json").write_bytes(canonical(manifest))
    result = score(root, "SYN-001")
    assert "not admitted" in result["reason"] and not result["trial_consumed"]


def test_journal_and_historical_ledger_cannot_be_erased(synthetic_repo):
    root, _, _ = synthetic_repo
    score(root, "SYN-001")
    base = commit(root, "Published receipt")
    (root / JOURNAL).write_bytes(b"")
    with pytest.raises(GateError, match="Append-only evidence rewritten"):
        verify_repository(root, base)
    (root / JOURNAL).write_bytes(git(root, "show", f"{base}:{JOURNAL}"))
    (root / "docs/research/TRIAL_LEDGER.md").write_text("Reset trial history\n")
    with pytest.raises(GateError, match="Append-only evidence rewritten"):
        verify_repository(root, base)


def test_forged_receipt_or_draft_cannot_kill_real_branch(tmp_path):
    folder = tmp_path / GOVERNANCE / "manifests"
    folder.mkdir(parents=True)
    (folder / "MOM-002.json").write_bytes(canonical({
        "schema": "rocket.research.manifest.v1", "experiment_id": "MOM-002",
        "safety_boundary": BOUNDARY, "state": "DRAFT", "scoring_authorized": False,
    }))
    with pytest.raises(GateError, match="Admitted experiment required"):
        disposition(tmp_path, {"experiment_id": "MOM-002", "phase": "FINISH", "record_sha256": "forged"},
                    audit={"receipt_sha256": "forged", "provenance_verified": True, "auditor": "external"})


def test_wip_and_admission_unlock_evidence_before_dispatch():
    item = {"id": "53", "primary_work_item": True, "status": "Ready", "priority": "P1",
            "admission_verified": True, "dependencies_verified": True,
            "unlock_verified": False, "kill_condition": "FAIL rejects downstream"}
    assert next_item([item]) is None
    item["unlock_verified"] = True
    assert next_item([item]) == item
    active = [{"primary_work_item": True, "status": "In Progress"} for _ in range(3)]
    with pytest.raises(GateError, match="WIP limit"):
        next_item(active + [item])


def test_hash_chain_tampering_detected(synthetic_repo):
    root, _, _ = synthetic_repo
    score(root, "SYN-001")
    raw = (root / JOURNAL).read_bytes().replace(b'"FAIL"', b'"PASS"')
    with pytest.raises(GateError, match="chain corrupted"):
        read_chain(raw)
