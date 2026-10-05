"""Synchronize only a committed, audited official MOM-002 receipt to its Project.

Run from the reviewed canonical checkout. Defaults to a reviewable JSON plan.
--apply writes deterministic fields; it never admits/decomposes a successor.
"""

import argparse
import json
import subprocess
from pathlib import Path

from rocket.research.governance import JOURNAL, GateError, disposition, git, read_chain, safe_path


def graphql(query: str, variables: dict) -> dict:
    result = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=json.dumps({"query": query, "variables": variables}),
        text=True, capture_output=True, check=True,
    )
    payload = json.loads(result.stdout)
    if payload.get("errors"):
        raise GateError(str(payload["errors"]))
    return payload["data"]


def plan(config: dict, receipt: dict, decision: dict) -> dict:
    outcome = decision["program_outcome"]
    updates = {item["id"]: {"Program Outcome": outcome} for item in config["items"].values()}
    updates[config["items"]["mom002"]["id"]].update({
        "Status": "Rejected" if decision.get("stop") else "Review / Gate",
        "Research State": {"FAIL": "Failed", "PASS": "Passed", "BLOCKED": "Blocked"}[receipt["result"]],
        "Trials Consumed": 1,
        "Evidence": f"{receipt['commit_sha']}; invocation {receipt['invocation_id']}; receipt {receipt['record_sha256']}",
    })
    downstream = updates[config["items"]["downstream"]["id"]]
    downstream["Status"] = decision["downstream_status"]
    downstream["Research State"] = "Failed" if decision.get("stop") else "Draft"
    return {"project_id": config["project"]["id"], "receipt_sha256": receipt["record_sha256"],
            "decision": decision, "updates": updates}


def apply(config: dict, update_plan: dict) -> None:
    fields = {f["name"]: f for f in config["fields"] if f}
    operations = []
    variables = {}
    for item_id, values in update_plan["updates"].items():
        for name, value in values.items():
            field = fields[name]
            if field["dataType"] == "SINGLE_SELECT":
                val = {"singleSelectOptionId": next(o["id"] for o in field["options"] if o["name"] == value)}
            elif field["dataType"] == "NUMBER":
                val = {"number": value}
            else:
                val = {"text": value}
            key = f"i{len(variables)}"
            variables[key] = {"projectId": update_plan["project_id"], "itemId": item_id,
                              "fieldId": field["id"], "value": val}
            operations.append(f"{key}:updateProjectV2ItemFieldValue(input:${key})" + "{projectV2Item{id}}")
    query = "mutation(" + ",".join(f"${key}:UpdateProjectV2ItemFieldValueInput!" for key in variables)
    graphql(query + "){" + "".join(operations) + "}", variables)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--audit", required=True, help="Committed repository-relative provenance audit JSON")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    records = read_chain((root / JOURNAL).read_bytes())
    receipt = next((r for r in records if r["record_sha256"] == args.receipt_sha256), None)
    if receipt is None:
        raise GateError("Receipt absent from canonical journal")
    audit_path = safe_path(root, args.audit)
    if git(root, "show", f"HEAD:{args.audit}") != audit_path.read_bytes():
        raise GateError("Provenance audit must be committed unchanged")
    if git(root, "show", f"HEAD:{JOURNAL}") != (root / JOURNAL).read_bytes():
        raise GateError("Journal receipt must be committed before Project disposition")
    decision = disposition(root, receipt, audit=json.loads(audit_path.read_bytes()))
    config = json.loads((root / "research/governance/project.json").read_bytes())
    update_plan = plan(config, receipt, decision)
    print(json.dumps(update_plan, indent=2))
    if args.apply:
        if git(root, "rev-parse", "HEAD") != git(root, "rev-parse", "origin/main"):
            raise GateError("Fetch and use reviewed main before applying gate disposition")
        apply(config, update_plan)


if __name__ == "__main__":
    main()
