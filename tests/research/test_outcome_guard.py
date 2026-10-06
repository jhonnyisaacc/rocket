"""Real-outcome access guard: y loads only under admitted scoring authority.

Draft state, flag flips without admission, and unknown experiments are
denied; the synthetic geometry path needs no authority. No market data,
real outcomes, or feature/outcome association is loaded here.
"""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rocket.research.governance import (
    BOUNDARY,
    GOVERNANCE,
    GateError,
    canonical,
    digest,
    git,
    require_real_outcome_authority,
)
from rocket.research.power import validate_geometry

DAY = 86_400_000


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_live_draft_manifest_denies_real_outcome_access():
    root = repo_root()
    manifest = json.loads((root / GOVERNANCE / "manifests/MOM-002.json").read_text())
    assert manifest["state"] == "DRAFT" and manifest["scoring_authorized"] is False
    assert manifest["trials_consumed"] == 0
    with pytest.raises(GateError, match="not admitted"):
        require_real_outcome_authority(root, "MOM-002")


def test_flag_flip_without_admission_still_denied(tmp_path):
    folder = tmp_path / GOVERNANCE / "manifests"
    folder.mkdir(parents=True)
    folder.joinpath("MOM-002.json").write_bytes(canonical({
        "schema": "rocket.research.manifest.v1", "experiment_id": "MOM-002",
        "safety_boundary": BOUNDARY, "state": "DRAFT", "scoring_authorized": True,
    }))
    with pytest.raises(GateError, match="Draft cannot authorize"):
        require_real_outcome_authority(tmp_path, "MOM-002")


def test_unknown_experiment_denied(tmp_path):
    with pytest.raises(GateError, match="No admission manifest"):
        require_real_outcome_authority(tmp_path, "MOM-999")


def admit_synthetic_repo(root: Path) -> dict:
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    git(root, "config", "user.name", "Synthetic test")
    git(root, "config", "user.email", "synthetic@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "config", "core.hooksPath", "/dev/null")
    artifacts = {}
    for role in ("contract", "population", "features", "model", "runtime"):
        path = root / (role + ".txt")
        path.write_text("Synthetic artifact: " + role)
        artifacts[role] = [{"path": path.name, "sha256": digest(path.read_bytes())}]
    scorer = root / "scorer.py"
    scorer.write_text("print('{\"experiment_id\": \"SYN-002\", \"result\": \"FAIL\"}')\n")
    artifacts["gate"] = [{"path": scorer.name, "sha256": digest(scorer.read_bytes())}]
    git(root, "add", ".")
    git(root, "commit", "-qm", "Synthetic pre-result artifacts")
    freeze = git(root, "rev-parse", "HEAD").decode().strip()
    manifest = {
        "schema": "rocket.research.manifest.v1", "experiment_id": "SYN-002",
        "family": "Synthetic", "state": "ADMITTED", "safety_boundary": BOUNDARY,
        "freeze_revision": freeze, "artifacts": artifacts, "trial_budget": 1,
        "trial_number": 1, "scoring_authorized": True, "proposer": "designer",
        "implementer": "builder",
        "scorer": {"path": "scorer.py", "protocol": "python-json-v1",
                   "timeout_seconds": 10, "python_version": sys.version},
        "approval": {"reviewer": "independent", "decision": "APPROVE",
                     "reviewed_revision": freeze,
                     "artifact_fingerprint": digest(canonical(artifacts)),
                     "timestamp": "2026-01-01T00:00:00+00:00",
                     "evidence": "Synthetic independent approval",
                     "review_provenance": {
                         "model_family": "synthetic-review-family",
                         "role": "independent reviewer",
                         "isolated_context": "Synthetic pre-result packet only",
                         "contribution_history": "No design or implementation contributions",
                         "designed_experiment": False, "implemented_experiment": False,
                         "outcomes_accessed": False}},
    }
    folder = root / GOVERNANCE / "manifests"
    folder.mkdir(parents=True)
    folder.joinpath("SYN-002.json").write_bytes(canonical(manifest))
    return manifest


def test_genuinely_admitted_manifest_authorizes(tmp_path):
    manifest = admit_synthetic_repo(tmp_path)
    assert require_real_outcome_authority(tmp_path, "SYN-002") == manifest


def synthetic_geometry():
    origin = int(datetime(2019, 1, 1, tzinfo=UTC).timestamp() * 1000)
    rows, ends, groups, next_time = [], {7: -1, 14: -1}, {7: -1, 14: -1}, -1
    for index in range(40):
        cutoff = origin + index * 7 * DAY
        decision = cutoff + 300_000
        year = datetime.fromtimestamp(decision / 1000, UTC).year
        for horizon in (7, 14):
            if decision > ends[horizon]:
                groups[horizon] += 1
            ends[horizon] = max(ends[horizon], cutoff + horizon * DAY)
        spaced = decision >= next_time
        if spaced:
            next_time = decision + 14 * DAY
        rows.append({"id": f"guard-synthetic-{index}", "cutoff": cutoff,
                     "decision_time": decision, "year": year, "fold": None,
                     "direction": 1 if index % 3 else -1, "scale": 0.05,
                     "component_7d": groups[7], "component_14d": groups[14],
                     "spaced": spaced, "horizon_supported": True})
    return {"schema": "rocket.power.geometry.v1", "rows": rows, "provenance": {
        "source_revision": "0" * 40, "causal_core_sha256": "0" * 64,
        "source_parser_sha256": "0" * 64, "source_files": [],
        "real_outcomes_accessed": False,
        "feature_completeness": "SYNTHETIC_ASSUMPTION",
        "coverage_assumption_start": "2020-09-01T00:00:00Z",
        "generator": "synthetic-only", "intervals": "[cutoff+5m,cutoff+horizon]"}}


def test_synthetic_geometry_needs_no_authority():
    assert validate_geometry(synthetic_geometry())["provenance"][
        "real_outcomes_accessed"] is False
