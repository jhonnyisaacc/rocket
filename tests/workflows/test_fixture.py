from rocket.models import Mode, ResearchStatus
from rocket.workflows.fixture import FixtureWorkflow
from tests.harness import assert_research_result


def test_fixture_scan_on_harness(now):
    result = FixtureWorkflow().scan(decision_time=now, available_at=now)
    assert_research_result(result)
    assert result.workflow == "fixture.scan"
    assert result.status is ResearchStatus.NO_SETUP


def test_replay_refuses_live_context(now):
    import pytest

    with pytest.raises(ValueError, match="live context"):
        FixtureWorkflow().scan(
            decision_time=now,
            available_at=now,
            mode=Mode.REPLAY,
            loaded_live_context=True,
        ).validate()
