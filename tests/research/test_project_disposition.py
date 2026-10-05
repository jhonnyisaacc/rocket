"""Project rejection plan covers the whole branch without admitting successors."""

import importlib.util
import json
from pathlib import Path

from rocket.research.governance import gate_decision


def test_fail_plan_rejects_branch_and_marks_outcome_on_all_existing_items():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("sync_gate", root / "scripts/research/sync_gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = json.loads((root / "research/governance/project.json").read_text())
    receipt = {"result": "FAIL", "record_sha256": "synthetic-receipt", "commit_sha": "synthetic-commit",
               "invocation_id": "synthetic-invocation"}
    update_plan = module.plan(config, receipt, gate_decision("FAIL"))
    assert set(update_plan["updates"]) == {i["id"] for i in config["items"].values()}
    assert all(v["Program Outcome"] == "Research Line Rejected" for v in update_plan["updates"].values())
    assert update_plan["updates"][config["items"]["downstream"]["id"]]["Status"] == "Rejected"
    assert update_plan["updates"][config["items"]["risk_charter"]["id"]]["Status"] == "Rejected"
    assert update_plan["updates"][config["items"]["risk_charter"]["id"]]["Research State"] == "Failed"
    assert update_plan["updates"][config["items"]["mom002"]["id"]]["Trials Consumed"] == 1
    assert update_plan["decision"]["successor_admitted"] is False
