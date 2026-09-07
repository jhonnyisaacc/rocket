import pytest

from rocket.models import (
    OperationalReport,
    OperationalStatus,
    ResearchResult,
    ResearchStatus,
    SafetyBoundary,
)
from rocket.workflows.fixture import FixtureWorkflow
from tests.harness import assert_research_result


def test_safety_boundary_is_always_human_gated(now):
    result = FixtureWorkflow().scan(decision_time=now, available_at=now)
    assert_research_result(result)
    assert result.safety_boundary is SafetyBoundary.READ_ONLY_RESEARCH_ONLY_HUMAN_GATED


def test_execution_enabled_true_is_rejected(now):
    with pytest.raises(ValueError, match="execution_enabled"):
        ResearchResult(
            workflow="fixture.scan",
            status=ResearchStatus.NO_SETUP,
            operational=OperationalReport(status=OperationalStatus.HEALTHY),
            decision_time=now,
            started_at=now,
            payload={"execution_enabled": True},
        ).validate()
