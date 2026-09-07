from rocket.models import OperationalStatus, ResearchStatus
from rocket.workflows.fixture import FixtureWorkflow
from tests.harness import WORKFLOWS, assert_research_result


def test_fixture_workflow_is_registered():
    assert "fixture.scan" in WORKFLOWS


def test_json_round_trip(now):
    result = FixtureWorkflow().scan(decision_time=now, available_at=now)
    assert_research_result(result)
    assert result.status is ResearchStatus.NO_SETUP
    assert result.operational.status is OperationalStatus.HEALTHY
