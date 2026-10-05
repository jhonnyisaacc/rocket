"""Decision tree behavior, with no invocation of the MOM-002 scorer."""

from rocket.research.governance import gate_decision


def test_fail_kills_entire_branch_and_stops_without_successor():
    assert gate_decision("FAIL") == {
        "downstream_status": "Rejected", "program_outcome": "Research Line Rejected",
        "stop": True, "successor_admitted": False,
    }


def test_pass_requires_human_acknowledgment_without_decomposition():
    outcome = gate_decision("PASS")
    assert outcome["downstream_status"] == "Parked"
    assert outcome["human_pass_acknowledgment_required"]
    assert outcome["successor_admitted"] is False


def test_blocked_preserves_killable_branch_without_rescue():
    outcome = gate_decision("BLOCKED")
    assert outcome["blocked"]
    assert outcome["downstream_status"] == "Parked"
    assert outcome["successor_admitted"] is False
