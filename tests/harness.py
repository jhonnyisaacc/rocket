"""Durable workflow harness. A workflow that is not registered cannot merge."""

from __future__ import annotations

from collections.abc import Mapping

from rocket.models import (
    Mode,
    OperationalStatus,
    ResearchResult,
    ResearchStatus,
    SafetyBoundary,
)
from rocket.pit import Availability
from rocket.workflows.fixture import FixtureWorkflow

WORKFLOWS: dict[str, type] = {
    "fixture.scan": FixtureWorkflow,
}

FORBIDDEN_SUBSTRINGS = (
    "~/.hermes",
    "~/.openclaw",
    "~/.nanobot",
    "HERMES_HOME",
    "channel-id",
    "discord_text",
    "openclaw",
    "nanobot",
)


def assert_research_result(result: ResearchResult) -> None:
    """Every registered workflow result must pass this. Called from all fixture tests."""
    result.validate()
    payload = result.to_dict()
    round_trip = ResearchResult.from_dict(payload)
    assert round_trip.to_dict() == payload
    assert result.safety_boundary is SafetyBoundary.READ_ONLY_RESEARCH_ONLY_HUMAN_GATED
    assert payload.get("execution_enabled") is not True
    assert result.payload.get("execution_enabled") is not True
    if result.mode is Mode.REPLAY:
        assert result.payload.get("loaded_live_context") is not True
    if result.operational.status is OperationalStatus.UNAVAILABLE:
        assert result.status not in {ResearchStatus.NO_SETUP, ResearchStatus.SETUP_FOUND}
    if result.status is ResearchStatus.SETUP_FOUND:
        assert any(item.availability is Availability.ELIGIBLE for item in result.evidence)
    if result.status is ResearchStatus.ERROR:
        assert result.warnings
    text = str(payload).lower()
    for marker in ("discord_text", "channel_id", "hermes_home"):
        assert marker not in text


def registered_names() -> tuple[str, ...]:
    return tuple(sorted(WORKFLOWS))


def is_registered(workflow: str) -> bool:
    return workflow in WORKFLOWS


def assert_payload_mapping(value: Mapping) -> None:
    assert isinstance(value, Mapping)
