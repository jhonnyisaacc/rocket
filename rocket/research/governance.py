"""Fail-closed direction admission, separate from strategy/experiment validation.

Files are reviewable operator records, not an authentication system. No execution
permission is granted. A changed evidence packet invalidates its workflow review.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE = ROOT / "docs/research/memecoin/RESEARCH_STATE.json"
CATEGORIES = {
    "evidence_summary",
    "feasibility_probe",
    "retrospective_discovery",
    "prospective_alpha",
    "infrastructure_calibration",
}
REOPEN = {
    "new_independent_data",
    "invalid_prior_test",
    "different_mechanism",
    "transfer_replication",
    "operator_decision",
}
CHECKS = {
    "stop_rule_complies",
    "family_evidence_considered",
    "mechanism_distinct",
    "decision_value",
    "infrastructure_justified",
    "operator_review_satisfied",
}


def read(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_state(state: dict) -> None:
    if state.get("schema") != "rocket.research-state.v1" or not nonempty(state.get("domain")):
        raise ValueError("invalid state schema/domain")
    if not isinstance(state.get("families"), dict) or not state["families"]:
        raise ValueError("families required")
    for family in state["families"].values():
        if not isinstance(family, dict):
            raise ValueError("family must be an object")
        if family.get("status") not in {
            "OPEN",
            "CANDIDATE",
            "KNOWN",
            "REJECTED",
            "REVIEW_REQUIRED",
        }:
            raise ValueError("invalid family status")
        if type(family.get("continuation_budget")) is not int or family["continuation_budget"] < 0:
            raise ValueError("invalid continuation budget")
        if type(family.get("operator_review_required")) is not bool:
            raise ValueError("operator review flag must be boolean")
        if (
            not isinstance(family.get("allowed_categories"), list)
            or not set(family["allowed_categories"]) <= CATEGORIES
        ):
            raise ValueError("invalid allowed categories")
        evidence = family.get("economic_evidence")
        if not isinstance(evidence, list):
            raise ValueError("economic evidence required")
        if any(
            not isinstance(row, dict)
            or not nonempty(row.get("cohort"))
            or row.get("outcome") not in {"NEGATIVE", "NONROBUST", "CANDIDATE", "INCONCLUSIVE"}
            for row in evidence
        ):
            raise ValueError("invalid economic evidence")
        cohorts = [row["cohort"] for row in evidence]
        if len(cohorts) != len(set(cohorts)):
            raise ValueError("economic evidence double counts cohort")


def packet(state: dict, checkpoint: dict) -> dict:
    validate_state(state)
    if checkpoint.get("schema") != "rocket.research-checkpoint.v1":
        raise ValueError("invalid checkpoint schema")
    for key in (
        "experiment",
        "hypothesis_family",
        "previous_result",
        "new_information",
        "decision_change",
        "mechanism_difference",
        "stop_rule_status",
        "work_kind",
        "proposer",
    ):
        if not nonempty(checkpoint.get(key)):
            raise ValueError(f"checkpoint requires {key}")
    if not re.fullmatch(r"[A-Z]+-[0-9]{3}", checkpoint["experiment"]):
        raise ValueError("invalid experiment id")
    if checkpoint.get("category") not in CATEGORIES:
        raise ValueError("invalid action category")
    if checkpoint["work_kind"] not in {
        "alpha_research",
        "infrastructure_calibration",
        "governance",
    }:
        raise ValueError("invalid work kind")
    for key in ("can_change_decision", "materially_different", "operator_review_required"):
        if type(checkpoint.get(key)) is not bool:
            raise ValueError(f"{key} must be boolean")
    if checkpoint.get("domain") != state["domain"]:
        raise ValueError("domain mismatch")
    family = state["families"].get(checkpoint["hypothesis_family"])
    if family is None:
        raise ValueError("unregistered family; reviewed state change required")
    if checkpoint.get("economic_gate_status") != family["economic_gate_status"]:
        raise ValueError("stale economic gate")
    if checkpoint["previous_result"] != family["last_evidence_checkpoint"]:
        raise ValueError("stale evidence checkpoint")
    documents = {}
    # Bounded paths fixed by repository policy, not arbitrary caller file reads.
    for name in (
        "docs/research/RESEARCH_CONSTITUTION.md",
        "docs/research/memecoin/MEMECOIN_PILLAR.md",
        "docs/research/memecoin/MEMECOIN_FRONTIER.md",
    ):
        documents[name] = (ROOT / name).read_text()
    design = checkpoint.get("design")
    if not isinstance(design, str):
        raise ValueError("design path required")
    path = (ROOT / design).resolve()
    if not path.is_relative_to(ROOT / "docs/research"):
        raise ValueError("design must be in docs/research")
    documents[design] = path.read_text()
    latest = family.get("latest_result_path")
    if latest:
        latest_path = (ROOT / latest).resolve()
        if not latest_path.is_relative_to(ROOT / "docs/research"):
            raise ValueError("result must be in docs/research")
        documents[latest] = latest_path.read_text()
    if sum(len(v) for v in documents.values()) > 100_000:
        raise ValueError("review packet exceeds 100k characters")
    return {
        "schema": "rocket.workflow-packet.v1",
        "state": state,
        "checkpoint": checkpoint,
        "documents": documents,
        "implementation_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "rocket/research/governance.py",
                "rocket/research/cli.py",
                "scripts/research/research_admission.cjs",
            )
        },
    }


def review(state: dict, checkpoint: dict, independent: dict | None = None) -> dict:
    bundle = packet(state, checkpoint)
    binding = digest(bundle)
    family = state["families"][checkpoint["hypothesis_family"]]
    reasons = []
    category = checkpoint["category"]
    reopening = family.get("reopening")
    reopened = (
        isinstance(reopening, dict)
        and reopening.get("condition") in REOPEN
        and reopening.get("experiment") == checkpoint["experiment"]
        and nonempty(reopening.get("evidence"))
        and nonempty(reopening.get("operator_authorization"))
    )
    if family["status"] in {"REJECTED", "REVIEW_REQUIRED"} and not reopened:
        reasons.append("FAMILY_STOPPED")
    if (
        family["operator_review_required"] or checkpoint["operator_review_required"]
    ) and not reopened:
        reasons.append("OPERATOR_REVIEW_REQUIRED")
    if category not in family["allowed_categories"] or category in family.get(
        "forbidden_categories", []
    ):
        reasons.append("CATEGORY_FORBIDDEN")
    if family["continuation_budget"] <= 0:
        reasons.append("CONTINUATION_BUDGET_EXHAUSTED")
    if state.get("active_experiment"):
        reasons.append("UNRESOLVED_ACTIVE_EXPERIMENT")
    if checkpoint["stop_rule_status"] != "CLEAR":
        reasons.append("STOP_RULE_NOT_CLEAR")
    if not checkpoint["can_change_decision"]:
        reasons.append("NO_STRATEGY_DECISION_VALUE")
    if category in {"retrospective_discovery", "prospective_alpha"} and (
        checkpoint["work_kind"] != "alpha_research" or not checkpoint["materially_different"]
    ):
        reasons.append("MECHANISM_NOT_DISTINCT_ALPHA")
    if category == "infrastructure_calibration" and (
        checkpoint["work_kind"] != "infrastructure_calibration"
        or not nonempty(checkpoint.get("alpha_dependency"))
    ):
        reasons.append("INFRASTRUCTURE_WITHOUT_ALPHA_DEPENDENCY")
    if independent is None:
        reasons.append("INDEPENDENT_REVIEW_MISSING")
    elif (
        independent.get("schema") != "rocket.workflow-review.v1"
        or independent.get("packet_sha256") != binding
        or independent.get("decision") != "WORKFLOW_OK"
        or not nonempty(independent.get("reviewer"))
        or independent.get("reviewer") == checkpoint.get("proposer")
        or not isinstance(independent.get("checks"), dict)
        or set(independent["checks"]) != CHECKS
        or any(v is not True for v in independent["checks"].values())
        or not isinstance(independent.get("reasons"), list)
    ):
        reasons.append("INDEPENDENT_REVIEW_INVALID_OR_BLOCKED")
    return {
        "schema": "rocket.workflow-gate.v1",
        "decision": "WORKFLOW_BLOCK" if reasons else "WORKFLOW_OK",
        "experiment": checkpoint["experiment"],
        "family": checkpoint["hypothesis_family"],
        "family_status": family["status"],
        "packet_sha256": binding,
        "reasons": reasons,
        "allowed_categories": family["allowed_categories"],
        "execution_enabled": False,
    }


@contextmanager
def locked(path: Path):
    lock = path.with_suffix(path.suffix + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        yield
    finally:
        os.close(fd)
        lock.unlink()


def save(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n")
    temp.replace(path)


def start(state_path: Path, checkpoint: dict, independent: dict) -> dict:
    with locked(state_path):
        state = read(state_path)
        decision = review(state, checkpoint, independent)
        if decision["decision"] != "WORKFLOW_OK":
            return decision
        experiment = checkpoint["experiment"]
        if experiment in state.get("admissions", {}):
            raise ValueError("experiment already admitted; never reuse ids")
        family = state["families"][checkpoint["hypothesis_family"]]
        family["continuation_budget"] -= 1
        state["active_experiment"] = experiment
        state.setdefault("admissions", {})[experiment] = {
            "checkpoint": checkpoint,
            "review": independent,
            "gate": decision,
            "started_at": datetime.now(UTC).isoformat(),
            "status": "STARTED",
        }
        save(state_path, state)
        return decision


def record_result(state_path: Path, result: dict) -> dict:
    """Each meaningful result suspends automatic continuation pending workflow review."""
    with locked(state_path):
        state = read(state_path)
        validate_state(state)
        experiment = state.get("active_experiment")
        if (
            not experiment
            or result.get("schema") != "rocket.direction-result.v1"
            or result.get("experiment") != experiment
        ):
            raise ValueError("result must match active admission")
        if result.get("outcome") not in {
            "NEGATIVE",
            "NONROBUST",
            "CANDIDATE",
            "INCONCLUSIVE",
            "CALIBRATION",
        }:
            raise ValueError("invalid direction outcome")
        if not nonempty(result.get("evidence")) or type(result.get("economic_test")) is not bool:
            raise ValueError("result requires evidence and economic_test boolean")
        if (
            result["outcome"] in {"NEGATIVE", "NONROBUST", "CANDIDATE"}
            and not result["economic_test"]
        ):
            raise ValueError("economic outcome cannot come from calibration")
        if result["economic_test"] and result["outcome"] == "CALIBRATION":
            raise ValueError("calibration is not an economic test")
        evidence_path = (ROOT / result["evidence"]).resolve()
        if not evidence_path.is_relative_to(ROOT / "docs/research"):
            raise ValueError("result evidence must be in docs/research")
        result["evidence_sha256"] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        admission = state["admissions"][experiment]
        family = state["families"][admission["checkpoint"]["hypothesis_family"]]
        if result["economic_test"]:
            if not nonempty(result.get("cohort")):
                raise ValueError("economic result requires independent cohort id")
            # Multiple tests on one cohort are retained, but never independent failures.
            old = next(
                (r for r in family["economic_evidence"] if r["cohort"] == result["cohort"]), None
            )
            if old:
                old.setdefault("dependent_results", []).append(result)
                if result["outcome"] in {"NEGATIVE", "NONROBUST"}:
                    old["outcome"] = result["outcome"]
            else:
                family["economic_evidence"].append(result)
        family["independent_economic_failures"] = sum(
            row["outcome"] in {"NEGATIVE", "NONROBUST"} for row in family["economic_evidence"]
        )
        family["consecutive_economic_failures"] = 0
        for row in reversed(family["economic_evidence"]):
            if row["outcome"] not in {"NEGATIVE", "NONROBUST"}:
                break
            family["consecutive_economic_failures"] += 1
        family.setdefault("research_debt", []).append(
            f"{experiment}: {result['outcome']}; direction review required before renewed investment"
        )
        family["latest_result_path"] = str(evidence_path.relative_to(ROOT))
        family["status"] = "REVIEW_REQUIRED"
        family["operator_review_required"] = True
        family["continuation_budget"] = 0
        family["last_evidence_checkpoint"] = experiment
        family["economic_gate_status"] = (
            result["outcome"] if result["economic_test"] else family["economic_gate_status"]
        )
        family.pop("reopening", None)
        admission.update(status="RESOLVED", result=result)
        state["active_experiment"] = None
        save(state_path, state)
        return {
            "decision": "WORKFLOW_BLOCK",
            "reason": "POST_RESULT_DIRECTION_REVIEW_REQUIRED",
            "family_status": family["status"],
            "execution_enabled": False,
        }


def require_experiment_step(experiment: str, step: str, state_path: Path | None = None) -> dict:
    """Internal steps reuse one reviewed admission; never reopen a direction."""
    state = read(state_path or DEFAULT_STATE)
    validate_state(state)
    admission = state.get("admissions", {}).get(experiment)
    if (
        not admission
        or state.get("active_experiment") != experiment
        or admission.get("status") != "STARTED"
    ):
        raise ValueError("WORKFLOW_BLOCK: experiment has no active admission")
    if step not in admission["checkpoint"].get("allowed_steps", []):
        raise ValueError("WORKFLOW_BLOCK: step outside approved experiment scope")
    prior = json.loads(json.dumps(state))
    prior["active_experiment"] = None
    prior["admissions"].pop(experiment)
    prior["families"][admission["checkpoint"]["hypothesis_family"]]["continuation_budget"] += 1
    decision = review(prior, admission["checkpoint"], admission["review"])
    if decision["decision"] != "WORKFLOW_OK":
        raise ValueError("WORKFLOW_BLOCK: stale reviewed experiment admission")
    return {
        "experiment": experiment,
        "step": step,
        "decision": "WORKFLOW_OK",
        "budget_consumed": False,
        "execution_enabled": False,
    }


def require_prospective_admission() -> None:
    """Used by prospective script entrypoints before any capture/network work."""
    state = read(DEFAULT_STATE)
    validate_state(state)
    experiment = os.environ.get("ROCKET_RESEARCH_EXPERIMENT")
    admission = state.get("admissions", {}).get(experiment)
    if (
        not admission
        or state.get("active_experiment") != experiment
        or admission.get("status") != "STARTED"
        or admission["checkpoint"]["category"]
        not in {"prospective_alpha", "infrastructure_calibration"}
    ):
        raise SystemExit(
            "WORKFLOW_BLOCK: prospective work requires rocket research start admission"
        )
    # Evaluate against the pre-admission snapshot; budget consumption is expected.
    prior = json.loads(json.dumps(state))
    prior["active_experiment"] = None
    prior["admissions"].pop(experiment)
    prior["families"][admission["checkpoint"]["hypothesis_family"]]["continuation_budget"] += 1
    decision = review(prior, admission["checkpoint"], admission["review"])
    if decision["decision"] != "WORKFLOW_OK":
        raise SystemExit("WORKFLOW_BLOCK: admission stale or direction no longer authorized")
