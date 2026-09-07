import pytest

from rocket.models import OperationalStatus, ResearchStatus
from rocket.workflows.fixture import FixtureWorkflow
from tests.harness import assert_research_result


def test_healthy_no_setup_is_valid(now):
    result = FixtureWorkflow().scan(
        decision_time=now,
        available_at=now,
        operational=OperationalStatus.HEALTHY,
        research=ResearchStatus.NO_SETUP,
    )
    assert_research_result(result)


def test_unavailable_cannot_claim_no_setup(now):
    with pytest.raises(ValueError, match="UNAVAILABLE"):
        FixtureWorkflow().scan(
            decision_time=now,
            available_at=now,
            operational=OperationalStatus.UNAVAILABLE,
            research=ResearchStatus.NO_SETUP,
        ).validate()


def test_unavailable_cannot_claim_setup_found(now):
    with pytest.raises(ValueError, match="UNAVAILABLE"):
        FixtureWorkflow().scan(
            decision_time=now,
            available_at=now,
            operational=OperationalStatus.UNAVAILABLE,
            research=ResearchStatus.SETUP_FOUND,
        ).validate()


def test_setup_found_requires_eligible_evidence(now):
    with pytest.raises(ValueError, match="eligible"):
        FixtureWorkflow().scan(
            decision_time=now,
            available_at=None,
            research=ResearchStatus.SETUP_FOUND,
        ).validate()


def test_error_requires_warning(now):
    with pytest.raises(ValueError, match="warning"):
        from rocket.models import OperationalReport, ResearchResult

        ResearchResult(
            workflow="fixture.scan",
            status=ResearchStatus.ERROR,
            operational=OperationalReport(status=OperationalStatus.ERROR),
            decision_time=now,
            started_at=now,
        ).validate()
