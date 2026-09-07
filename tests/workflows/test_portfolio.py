from datetime import UTC, datetime

from rocket.models import OperationalStatus, ResearchStatus
from rocket.workflows.portfolio import (
    PortfolioState,
    PositionState,
    apply_inventory,
    review_positions,
)
from tests.harness import assert_research_result, is_registered

NOW = datetime(2026, 9, 4, 15, tzinfo=UTC)


def test_portfolio_is_registered():
    assert is_registered("portfolio.review")


def test_private_state_age_not_market_missingness_and_per_position_failure():
    state = PortfolioState(
        updated_at="2026-08-01T00:00:00Z",
        positions=(
            PositionState("GOOD", thesis="Recorded thesis"),
            PositionState("MISSING"),
        ),
    )
    result = review_positions(
        state,
        {
            "GOOD": {
                "macro_regime": "neutral",
                "technical_condition": "healthy",
                "market_state": {"current_price": 100, "as_of": NOW.isoformat(), "source": "fixture"},
            }
        },
        now=NOW,
    )
    assert_research_result(result)
    assert [row["action"] for row in result.payload["positions"]] == ["HOLD", "REVIEW_REQUIRED"]
    assert result.status is ResearchStatus.ACTION_REQUIRED
    assert result.operational.status is OperationalStatus.HEALTHY


def test_empty_state_is_caller_missing_not_no_setup():
    result = review_positions(PortfolioState(), {}, now=NOW)
    assert_research_result(result)
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert "CALLER_STATE_MISSING" in result.warnings[0]


def test_inventory_updates_quantity_without_creating_positions_or_theses():
    state = PortfolioState(
        positions=(PositionState("MSFT", thesis="keep", thesis_status="RECORDED", quantity=1),)
    )
    updated = apply_inventory(state, {"MSFT": {"ticker": "MSFT", "quantity": 3}, "NVDA": {"ticker": "NVDA", "quantity": 9}})
    assert len(updated.positions) == 1
    assert updated.positions[0].quantity == 3
    assert updated.positions[0].thesis == "keep"
    assert updated.positions[0].thesis_status == "RECORDED"
