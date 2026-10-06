"""Small Git-backed freeze verifier and single-trial official scoring journal.

Hashes prove integrity, not scientific independence or unseen outcome access.
Independent experiment review is recorded in artifacts, independent of GitHub permissions.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

GOVERNANCE = "research/governance"
JOURNAL = f"{GOVERNANCE}/invocations.jsonl"
FROZEN = {"FROZEN", "ADMITTED"}
ROLES = {"contract", "population", "features", "model", "gate", "runtime"}
BOUNDARY = "READ_ONLY_RESEARCH_ONLY_HUMAN_GATED"


class GateError(ValueError):
    """Missing authority or integrity; never reinterpret as a scientific PASS."""


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise GateError("Git provenance unavailable: " + " ".join(args))
    return result.stdout


def safe_path(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise GateError("Artifact path must be repository-relative")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise GateError("Artifact escapes repository")
    if resolved != root.resolve() / candidate:
        raise GateError("Symlink artifacts are not admissible")
    return resolved


def manifest_path(root: Path, experiment_id: str) -> Path:
    if not re.fullmatch(r"[A-Z][A-Z0-9-]{1,63}", experiment_id):
        raise GateError("Invalid experiment identity")
    return safe_path(root, f"{GOVERNANCE}/manifests/{experiment_id}.json")


def verify_manifest(root: Path, manifest: dict) -> None:
    if not isinstance(manifest, dict):
        raise GateError("Manifest must be a JSON object")
    if manifest.get("schema") != "rocket.research.manifest.v1":
        raise GateError("Unknown manifest schema")
    if manifest.get("safety_boundary") != BOUNDARY:
        raise GateError("Research safety boundary required")
    if manifest.get("state") == "DRAFT":
        if manifest.get("scoring_authorized") is not False:
            raise GateError("Draft cannot authorize scoring")
        return
    if manifest.get("state") not in FROZEN:
        raise GateError("Unknown manifest state")
    if manifest.get("experiment_id") == "MOM-002":
        from rocket.research.policy import mom002_prerequisites
        mom002_prerequisites(root, manifest)
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict) or not ROLES <= artifacts.keys() or not all(artifacts[r] for r in ROLES):
        raise GateError("All six frozen artifact roles required")
    revision = manifest["freeze_revision"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise GateError("Full preregistration Git SHA required")
    git(root, "merge-base", "--is-ancestor", revision, "HEAD")
    for entries in artifacts.values():
        for entry in entries:
            path = safe_path(root, entry["path"])
            frozen_bytes = git(root, "show", f"{revision}:{entry['path']}")
            if digest(frozen_bytes) != entry["sha256"] or digest(path.read_bytes()) != entry["sha256"]:
                raise GateError(f"Frozen artifact changed: {entry['path']}")
    gate_paths = {e["path"] for e in artifacts["gate"]}
    if manifest.get("scorer", {}).get("path") not in gate_paths:
        raise GateError("Scorer must be part of the frozen gate")
    if manifest["scorer"].get("protocol") != "python-json-v1":
        raise GateError("Unknown scorer protocol")
    if not manifest["scorer"].get("python_version"):
        raise GateError("Frozen Python version required")
    if type(manifest["scorer"].get("timeout_seconds")) is not int or not 1 <= manifest["scorer"]["timeout_seconds"] <= 86400:
        raise GateError("Explicit bounded scorer timeout required")
    if type(manifest.get("trial_budget")) is not int or manifest["trial_budget"] != 1 or type(manifest.get("trial_number")) is not int:
        raise GateError("Explicit single-trial budget/number required")
    if manifest["trial_number"] < 1:
        raise GateError("Trial number must be positive")
    if manifest.get("state") == "ADMITTED":
        approval = manifest.get("approval", {})
        if not isinstance(approval, dict):
            raise GateError("Independent approval object required")
        reviewer = approval.get("reviewer")
        identities = [manifest.get("proposer"), manifest.get("implementer"), reviewer]
        if any(not isinstance(i, str) or not i.strip() or any(
            placeholder in i.upper() for placeholder in ("UNRESOLVED", "UNASSIGNED", "HUMAN_DECISION_REQUIRED")
        ) for i in identities):
            raise GateError("Resolved contributor/reviewer identities required")
        if not reviewer or reviewer == manifest.get("proposer") or reviewer == manifest.get("implementer"):
            raise GateError("Independent reviewer required")
        provenance = approval.get("review_provenance")
        if not isinstance(provenance, dict) or any(
            not isinstance(provenance.get(field), str) or not provenance[field].strip()
            for field in ("model_family", "role", "isolated_context", "contribution_history")
        ):
            raise GateError("Scientific review role/model/context/contribution provenance required")
        if any(provenance.get(field) is not False for field in (
            "designed_experiment", "implemented_experiment", "outcomes_accessed"
        )):
            raise GateError("Scientific reviewer must be independent and pre-result")
        if approval.get("decision") != "APPROVE" or approval.get("reviewed_revision") != revision:
            raise GateError("Approval must name exact frozen revision")
        if approval.get("artifact_fingerprint") != digest(canonical(artifacts)):
            raise GateError("Approval does not match frozen artifacts")
        if not approval.get("evidence") or not approval.get("timestamp"):
            raise GateError("Approval provenance required")
        approved_at = datetime.fromisoformat(approval["timestamp"])
        if approved_at.tzinfo is None or approved_at > datetime.now(UTC):
            raise GateError("Approval must precede scoring with an aware timestamp")
        if manifest.get("scoring_authorized") is not True:
            raise GateError("Admitted scoring authority absent")


def require_real_outcome_authority(root: Path, experiment_id: str) -> dict:
    """Mandatory choke point before loading real experiment outcomes (y).

    Synthetic geometry/provenance paths never call this function. Raises
    GateError unless the admission manifest verifies, the experiment is
    ADMITTED, and scoring authority is True. Nothing here inspects
    outcomes, fits models, or scores.
    """
    try:
        raw = manifest_path(root, experiment_id).read_bytes()
    except (OSError, GateError) as exc:
        raise GateError(f"No admission manifest for {experiment_id}") from exc
    try:
        manifest = json.loads(raw)
    except ValueError as exc:
        raise GateError(f"Admission manifest is not JSON for {experiment_id}") from exc
    verify_manifest(root, manifest)
    if manifest.get("state") != "ADMITTED":
        raise GateError(f"Real outcomes are locked: {experiment_id} is not admitted")
    if manifest.get("scoring_authorized") is not True:
        raise GateError(f"Real outcomes are locked: {experiment_id} scoring is not authorized")
    return manifest


def read_chain(raw: bytes) -> list[dict]:
    previous = None
    records = []
    for line in raw.splitlines():
        record = json.loads(line)
        claimed = record.pop("record_sha256")
        if record.get("previous_sha256") != previous or digest(canonical(record)) != claimed:
            raise GateError("Scoring journal chain corrupted")
        record["record_sha256"] = claimed
        previous = claimed
        records.append(record)
    if raw and not raw.endswith(b"\n"):
        raise GateError("Incomplete journal receipt")
    return records


def append_record(handle, record: dict, previous: str | None) -> dict:
    receipt = dict(record, previous_sha256=previous)
    receipt["record_sha256"] = digest(canonical(receipt))
    handle.seek(0, os.SEEK_END)
    handle.write(canonical(receipt) + b"\n")
    handle.flush()
    os.fsync(handle.fileno())
    return receipt


def at_revision(root: Path, revision: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{revision}:{path}"], capture_output=True, check=False
    )
    return result.stdout if result.returncode == 0 else None


def verify_repository(root: Path, base: str | None = None) -> dict:
    project_path = root / GOVERNANCE / "project.json"
    if project_path.exists():
        from rocket.research.policy import authority
        authority(root)
    elif base and at_revision(root, base, f"{GOVERNANCE}/project.json") is not None:
        raise GateError("Authoritative Project policy deleted")
    folder = root / GOVERNANCE / "manifests"
    current = {p.relative_to(root).as_posix(): p for p in folder.glob("*.json")}
    for relative, path in current.items():
        manifest = json.loads(path.read_bytes())
        if path != manifest_path(root, manifest["experiment_id"]):
            raise GateError("Manifest filename/identity mismatch")
        verify_manifest(root, manifest)
    raw = (root / JOURNAL).read_bytes()
    records = read_chain(raw)
    for line in (root / GOVERNANCE / "invalidations.jsonl").read_text().splitlines():
        invalidation = json.loads(line)
        if not all(invalidation.get(k) for k in ("experiment_id", "timestamp", "reason", "evidence", "reviewer")):
            raise GateError("Invalidation provenance required")
        if not manifest_path(root, invalidation["experiment_id"]).exists():
            raise GateError("Invalidation references missing original experiment")
    if base:
        git(root, "rev-parse", "--verify", base)
        old_paths = git(root, "ls-tree", "-r", "--name-only", base, f"{GOVERNANCE}/manifests").decode().splitlines()
        for relative in old_paths:
            old = at_revision(root, base, relative)
            if not relative.endswith(".json") or old is None:
                continue
            manifest = json.loads(old)
            if manifest.get("state") in FROZEN:
                if relative not in current or current[relative].read_bytes() != old:
                    raise GateError("Frozen manifest changed/deleted; append invalidation, use new trial")
                verify_manifest(root, manifest)
        for relative in (JOURNAL, "docs/research/TRIAL_LEDGER.md", f"{GOVERNANCE}/invalidations.jsonl"):
            old = at_revision(root, base, relative)
            if old is not None:
                new = safe_path(root, relative).read_bytes()
                if not new.startswith(old):
                    raise GateError(f"Append-only evidence rewritten: {relative}")
    return {"status": "VERIFIED", "manifests": len(current), "journal_records": len(records)}


def score(root: Path, experiment_id: str) -> dict:
    """One official attempt. No caller result input or ignore-freeze option."""
    journal = safe_path(root, JOURNAL)
    with journal.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        records = read_chain(handle.read())
        previous = records[-1]["record_sha256"] if records else None
        now = datetime.now(UTC).isoformat()
        receipt = {
            "schema": "rocket.research.invocation.v1", "invocation_id": str(uuid.uuid4()),
            "experiment_id": experiment_id, "timestamp": now, "commit_sha": None,
            "frozen_hashes": {}, "dataset_fingerprint": None, "trial_number": None,
            "result_fingerprint": None, "scorer": None, "result": "BLOCKED",
            "phase": "PREFLIGHT", "trial_consumed": False,
        }
        try:
            receipt["commit_sha"] = git(root, "rev-parse", "HEAD").decode().strip()
            manifest = json.loads(manifest_path(root, experiment_id).read_bytes())
            if not isinstance(manifest, dict):
                raise GateError("Manifest must be a JSON object")
            receipt.update(frozen_hashes=manifest.get("artifacts", {}),
                           trial_number=manifest.get("trial_number"), scorer=manifest.get("scorer"))
            verify_manifest(root, manifest)
            if manifest["state"] != "ADMITTED":
                raise GateError("Experiment is not admitted/frozen for scoring")
            if manifest["scorer"]["python_version"] != sys.version:
                raise GateError("Interpreter differs from admitted runtime")
            if receipt["commit_sha"] != git(root, "rev-parse", "origin/main").decode().strip():
                raise GateError("Official scoring requires canonical main; fetch main before invocation")
            if git(root, "status", "--porcelain", "--untracked-files=all").strip():
                raise GateError("Official scoring requires a clean canonical checkout")
            if at_revision(root, "HEAD", manifest_path(root, experiment_id).relative_to(root).as_posix()) is None:
                raise GateError("Admission manifest must be committed")
            invalidations = safe_path(root, f"{GOVERNANCE}/invalidations.jsonl").read_text()
            if any(json.loads(line)["experiment_id"] == experiment_id for line in invalidations.splitlines()):
                raise GateError("Experiment explicitly invalidated; new admission/trial required")
            if any(r["experiment_id"] == experiment_id and r.get("trial_consumed") for r in records):
                raise GateError("Trial already started; no repeated outcome access")
            dataset = manifest["dataset"]
            data_path = safe_path(root, dataset["path"])
            receipt["dataset_fingerprint"] = digest(data_path.read_bytes())
            if receipt["dataset_fingerprint"] != dataset["sha256"]:
                raise GateError("Dataset differs from admitted fingerprint")
            receipt.update(phase="START", trial_consumed=True, result=None)
            start = append_record(handle, receipt, previous)
            previous = start["record_sha256"]
            scorer = safe_path(root, manifest["scorer"]["path"])
            completed = subprocess.run(
                [sys.executable, "-I", str(scorer), str(data_path)], cwd=root,
                env={"PATH": os.defpath, "LANG": "C.UTF-8"}, capture_output=True,
                timeout=manifest["scorer"]["timeout_seconds"], check=False,
            )
            receipt["result_fingerprint"] = digest(completed.stdout + b"\0" + completed.stderr)
            if completed.returncode:
                raise GateError("Frozen scorer failed; reserved trial consumed")
            result = json.loads(completed.stdout)
            if not isinstance(result, dict):
                raise GateError("Scorer must emit one JSON gate object")
            canonical(result)
            verify_manifest(root, manifest)
            if digest(data_path.read_bytes()) != receipt["dataset_fingerprint"]:
                raise GateError("Dataset mutated during scoring; trial consumed")
            if result.get("experiment_id") != experiment_id or result.get("result") not in {"PASS", "FAIL", "BLOCKED"}:
                raise GateError("Scorer returned invalid gate identity/result")
            receipt.update(result=result["result"], phase="FINISH", details=result)
        except (GateError, OSError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
            receipt.update(result="BLOCKED", phase="FINISH" if receipt["trial_consumed"] else "PREFLIGHT",
                           reason=str(exc))
        if receipt["result_fingerprint"] is None:
            receipt["result_fingerprint"] = digest(canonical({"result": receipt["result"], "reason": receipt.get("reason")}))
        return append_record(handle, receipt, previous)


def next_item(snapshot: dict, wip_limit: int = 3, *, root: Path | None = None) -> dict | None:
    """Repository policy and Project membership govern dispatch, never issue ordering."""
    from rocket.research.policy import select_next
    return select_next(root or Path(__file__).resolve().parents[2], snapshot, wip_limit)


def disposition(root: Path, receipt: dict, *, audit: dict) -> dict:
    if receipt.get("experiment_id") != "MOM-002" or receipt.get("phase") != "FINISH":
        raise GateError("MOM-002 terminal scorer receipt required")
    if audit.get("receipt_sha256") != receipt.get("record_sha256") or audit.get("provenance_verified") is not True:
        raise GateError("Audited exact receipt required")
    manifest = json.loads(manifest_path(root, "MOM-002").read_bytes())
    verify_manifest(root, manifest)
    if manifest.get("state") != "ADMITTED":
        raise GateError("Admitted experiment required for disposition")
    auditor = audit.get("auditor")
    if not isinstance(auditor, str) or not auditor.strip() or auditor in {manifest.get("proposer"), manifest.get("implementer")} or "UNRESOLVED" in auditor.upper():
        raise GateError("Independent provenance audit required")
    records = read_chain((root / JOURNAL).read_bytes())
    if receipt not in records or not receipt.get("trial_consumed"):
        raise GateError("Canonical consumed-trial receipt required")
    if not any(r["invocation_id"] == receipt["invocation_id"] and r["phase"] == "START" for r in records):
        raise GateError("Scoring START provenance missing")
    return gate_decision(receipt.get("result"))


def gate_decision(result: str) -> dict:
    """Pure decision tree, used only after canonical receipt/admission/audit checks."""
    if result == "FAIL":
        return {"downstream_status": "Rejected", "program_outcome": "Research Line Rejected",
                "stop": True, "successor_admitted": False}
    if result == "PASS":
        return {"downstream_status": "Parked", "program_outcome": "Active",
                "human_pass_acknowledgment_required": True, "successor_admitted": False}
    return {"downstream_status": "Parked", "program_outcome": "Active",
            "blocked": True, "successor_admitted": False}
