"""Repository authority for dispatch, review tiers, prerequisites and PR actions."""

import json
import re
from datetime import UTC, datetime

from rocket.research.governance import (
    GOVERNANCE,
    JOURNAL,
    GateError,
    digest,
    git,
    read_chain,
    safe_path,
)

TIERS = {"MAINTENANCE", "FOUNDATION", "SCIENTIFIC_ADMISSION", "PROSPECTIVE_VALIDATION", "CAPITAL"}
GATE_SOURCES = {"CODE", "HUMAN", "DATA", "REVIEW", "NONE"}
DISPOSITIONS = {"CONTINUE_ACTIVE", "MERGE_WHEN_ACCEPTED", "CLOSE_EVIDENCE_ARCHIVE", "SUPERSEDED", "BLOCKED"}
PREREQUISITES = {"foundation", "tier_b_readiness", "overlap_semantics", "power_audit",
                 "pre_result_contract", "near_term_human_decisions"}
PREREQUISITE_PATH = f"{GOVERNANCE}/mom002_prerequisites.json"


def authority(root):
    config = json.loads(safe_path(root, f"{GOVERNANCE}/project.json").read_bytes())
    if config.get("wip_limit") != 3 or config.get("schema") != "rocket.research.project.v1":
        raise GateError("Authoritative Project/WIP contract required")
    ids = [item["id"] for item in config["items"].values()]
    if len(ids) != len(set(ids)):
        raise GateError("Project item registry identities must be unique")
    for key in config["primary_work_item_keys"]:
        item = config["items"][key]
        fields = item["fields"]
        if fields.get("Review Tier") not in TIERS or fields.get("Gate Source") not in GATE_SOURCES:
            raise GateError("Review Tier and Gate Source contract required")
        budget, consumed = fields.get("Trial Budget"), fields.get("Trials Consumed")
        if type(budget) is not int or type(consumed) is not int or not 0 <= consumed <= budget:
            raise GateError("Distinct nonnegative trial budget/consumed counts required")
        if fields["Review Tier"] == "MAINTENANCE" and budget != 0:
            raise GateError("Maintenance cannot reserve alpha trials")
    return config


def mom002_prerequisites(root, manifest=None):
    value = json.loads(safe_path(root, PREREQUISITE_PATH).read_bytes())
    if value.get("schema") != "rocket.mom002.prerequisites.v1" or set(value.get("requirements", {})) != PREREQUISITES:
        raise GateError("Complete MOM-002 pre-result prerequisite contract required")
    if value.get("outcome_accessed") is not False:
        raise GateError("MOM-002 prerequisite acceptance must precede outcome access")
    for name, record in value["requirements"].items():
        if record.get("status") != "ACCEPTED":
            raise GateError(f"MOM-002 prerequisite not accepted: {name}")
    for name, record in value["requirements"].items():
        if not all(record.get(k) for k in ("reviewer", "evidence", "timestamp", "reviewed_revision", "artifacts")):
            raise GateError(f"Exact prerequisite acceptance evidence required: {name}")
        if not re.fullmatch(r"[0-9a-f]{40}", record["reviewed_revision"]):
            raise GateError("Prerequisite acceptance requires exact Git revision")
        if any(p in record["reviewer"].upper() for p in ("UNRESOLVED", "UNASSIGNED", "HUMAN_DECISION_REQUIRED")):
            raise GateError("Resolved prerequisite reviewer required")
        accepted_at = datetime.fromisoformat(record["timestamp"])
        if accepted_at.tzinfo is None or accepted_at > datetime.now(UTC):
            raise GateError("Prerequisite acceptance must have a past aware timestamp")
        for entry in record["artifacts"]:
            if digest(safe_path(root, entry["path"]).read_bytes()) != entry["sha256"]:
                raise GateError("Accepted prerequisite artifact changed")
            if digest(git(root, "show", f"{record['reviewed_revision']}:{entry['path']}")) != entry["sha256"]:
                raise GateError("Prerequisite artifacts differ from accepted Git revision")
        if name in {"near_term_human_decisions", "pre_result_contract"} and record.get("human_decision_recorded") is not True:
            raise GateError("Required human decisions/final pre-result disposition absent")
        if name == "power_audit":
            if record.get("predictive_trials_consumed") != 0 or record.get("real_outcomes_accessed") is not False:
                raise GateError("Power audit must be zero-trial and outcome-free")
            if record.get("pre_result_review_resolved") is not True:
                raise GateError("Power audit requires resolved pre-result gate review")
    if manifest is not None:
        entries = manifest.get("artifacts", {}).get("contract", [])
        if not any(e["path"] == PREREQUISITE_PATH for e in entries):
            raise GateError("Freeze must hash prerequisite acceptance contract")
        approved = value["requirements"]["pre_result_contract"]["artifacts"]
        final_paths = {e["path"]: e["sha256"] for e in approved}
        if not final_paths or not any(e["path"] in final_paths and e["sha256"] == final_paths[e["path"]] for e in entries):
            raise GateError("Freeze must include final post-power-audit contract")
    return value


def pr_action(config, number, accepted_blockers=()):
    """Reviewable plan only. An open historical PR never grants research permission."""
    record = config["pr_dispositions"].get(str(number))
    if record is None or record.get("disposition") not in DISPOSITIONS:
        raise GateError("Explicit repository PR disposition required")
    missing = [b["id"] for b in record["blockers"] if b["id"] not in accepted_blockers]
    action = "KEEP_OPEN"
    if not missing:
        if record["disposition"] == "MERGE_WHEN_ACCEPTED":
            action = "AWAIT_AUTHORIZED_MERGER"
        elif record["disposition"] == "CLOSE_EVIDENCE_ARCHIVE":
            action = "READY_FOR_DOCUMENTED_EVIDENCE_CLOSURE"
    return {"pr": number, "disposition": record["disposition"], "missing_blockers": missing,
            "action": action, "research_admitted": False, "agent_merge_authorized": False}


def select_next(root, snapshot, wip_limit=3):
    config = authority(root)
    if snapshot.get("project_id") != config["project"]["id"]:
        raise GateError("Only canonical Project members can be dispatched")
    contracts = {config["items"][key]["id"]: (key, config["items"][key]) for key in config["primary_work_item_keys"]}
    inventory = [i.get("id") for i in snapshot["items"] if i.get("id") in contracts]
    if set(inventory) != set(contracts):
        raise GateError("Complete canonical primary inventory required for WIP")
    if len(inventory) != len(set(inventory)):
        raise GateError("Duplicate primary WIP item")
    items = []
    seen = set()
    for item in snapshot["items"]:
        if item.get("id") not in contracts:
            continue
        if item["id"] in seen:
            raise GateError("Duplicate primary WIP item")
        seen.add(item["id"])
        key, contract = contracts[item["id"]]
        if item.get("project_id") != config["project"]["id"] or item.get("repository") != "jhonnyisaacc/rocket":
            raise GateError("Canonical member Project/repository identity mismatch")
        if item.get("research_state") in {"Historical", "Failed"} or item.get("operational_service") is True:
            continue
        items.append((key, contract, item))
    if sum(i["status"] in {"In Progress", "Review / Gate"} for _, _, i in items) >= min(wip_limit, config["wip_limit"]):
        raise GateError("Research WIP limit reached")
    ready = []
    invocations = read_chain(safe_path(root, JOURNAL).read_bytes())
    for key, contract, item in items:
        fields = contract["fields"]
        if item.get("primary_work_item") is not True:
            continue
        if fields["Gate Source"] == "HUMAN" or fields["Review Tier"] == "CAPITAL":
            continue
        if item.get("status") != "Ready" or not all(item.get(k) is True for k in ("admission_verified", "unlock_verified", "dependencies_verified")):
            continue
        if not item.get("kill_condition") or fields["Trials Consumed"] >= fields["Trial Budget"] > 0:
            continue
        if any(item.get(k) != fields[field] for k, field in (("review_tier", "Review Tier"), ("gate_source", "Gate Source"), ("trial_budget", "Trial Budget"), ("trials_consumed", "Trials Consumed"))):
            raise GateError("Project snapshot cannot override repository review/trial policy")
        if key in {"mom002", "review"}:
            mom002_prerequisites(root)
        if fields["Review Tier"] in {"SCIENTIFIC_ADMISSION", "PROSPECTIVE_VALIDATION"}:
            if item.get("isolated_review_package_verified") is not True:
                continue
            if key != "review":
                from rocket.research.governance import verify_manifest
                experiment_id = contract.get("experiment_id")
                if not experiment_id:
                    continue
                if item.get("experiment_id") != experiment_id:
                    raise GateError("Snapshot cannot substitute another experiment manifest")
                if any(r.get("experiment_id") == experiment_id and r.get("trial_consumed") for r in invocations):
                    continue
                manifest = json.loads(safe_path(root, f"{GOVERNANCE}/manifests/{experiment_id}.json").read_bytes())
                verify_manifest(root, manifest)
                if manifest.get("state") != "ADMITTED":
                    continue
        ready.append((fields["Priority"], key, item))
    return min(ready, key=lambda entry: entry[:2])[2] if ready else None
