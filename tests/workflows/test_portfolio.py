from datetime import UTC, datetime

from rocket.models import OperationalStatus, ResearchStatus
from rocket.providers.inventory import FileInventory
from rocket.store import ResearchStore
from rocket.workflows.portfolio import (
    PortfolioState,
    PortfolioWorkflow,
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
                "market_state": {"current_price": 100, "as_of": NOW.isoformat(), "available_at": NOW.isoformat(), "source": "fixture"},
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


def test_refresh_without_address_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.delenv("ROCKET_INVENTORY_ADDRESS", raising=False)
    state = PortfolioState(positions=(PositionState("MSFT", thesis="keep", quantity=1),), updated_at=NOW.isoformat())
    result = PortfolioWorkflow(store=ResearchStore(tmp_path), inventory=FileInventory()).run(
        state,
        {"MSFT": {"macro_regime": "neutral", "technical_condition": "healthy", "market_state": {"current_price": 1, "as_of": NOW.isoformat(), "available_at": NOW.isoformat(), "source": "fixture"}}},
        now=NOW,
        refresh_inventory=True,
    )
    assert_research_result(result)
    assert result.operational.status is OperationalStatus.UNAVAILABLE
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE


def test_pending_ondo_mints_are_surfaced(tmp_path):
    inventory = FileInventory(
        (
            {"ticker": "MSFT", "quantity": 4},
            {"ticker": "UNKNOWN", "mint": "mysteryondo", "quantity": 2, "pending_review": True},
        )
    )
    state = PortfolioState(
        wallet_address="abc",
        updated_at=NOW.isoformat(),
        positions=(PositionState("MSFT", thesis="keep", quantity=1),),
    )
    result = PortfolioWorkflow(store=ResearchStore(tmp_path), inventory=inventory).run(
        state,
        {"MSFT": {"macro_regime": "neutral", "technical_condition": "healthy", "market_state": {"current_price": 1, "as_of": NOW.isoformat(), "available_at": NOW.isoformat(), "source": "fixture"}}},
        now=NOW,
        refresh_inventory=True,
    )
    assert_research_result(result)
    assert result.payload["positions"][0]["quantity"] == 4
    assert result.payload["pending_review"][0]["mint"] == "mysteryondo"
