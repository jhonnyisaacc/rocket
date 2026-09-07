from datetime import UTC, datetime

from rocket.models import OperationalStatus, ResearchStatus
from rocket.workflows.watch import check_watch
from tests.harness import assert_research_result, is_registered

NOW = datetime(2026, 9, 7, 15, tzinfo=UTC)


def test_watch_is_registered():
    assert is_registered("watch.check")


def test_partial_watch_evaluates_supported_rule_without_false_trigger():
    watches = [
        {"ticker": "CAT", "condition": "BELOW", "threshold": 740},
        {"ticker": "UNKNOWN", "condition": "BELOW", "threshold": 100},
    ]
    result = check_watch(watches, {"CAT": 810}, now=NOW)
    assert_research_result(result)
    assert result.status is ResearchStatus.NO_SETUP
    assert result.payload["coverage_status"] == "PARTIAL"
    assert result.payload["valid_watch_count"] == 2
    assert result.payload["evaluated_count"] == 1
    assert result.payload["unavailable_prices"] == ["UNKNOWN"]
    assert not result.payload["events"]


def test_missing_condition_is_invalid_not_default_zone():
    result = check_watch([{"ticker": "CAT", "threshold": 100}], {"CAT": 90}, now=NOW)
    assert_research_result(result)
    assert "CAT" in result.payload["invalid_watches"]
    assert result.payload["model_escalation"] is False


def test_event_is_action_required():
    result = check_watch([{"ticker": "CAT", "condition": "BELOW", "threshold": 800}], {"CAT": 700}, now=NOW)
    assert_research_result(result)
    assert result.status is ResearchStatus.ACTION_REQUIRED
    assert result.operational.status is OperationalStatus.HEALTHY
    assert result.payload["events"][0]["ticker"] == "CAT"
