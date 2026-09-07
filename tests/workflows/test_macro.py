from datetime import UTC, datetime, timedelta

from rocket.models import OperationalStatus, ResearchStatus
from rocket.workflows.macro import FACTORS, MacroWorkflow, macro_is_usable
from tests.harness import assert_research_result, is_registered

NOW = datetime(2026, 9, 7, 15, tzinfo=UTC)


def _fetcher(symbol: str):
    records = [
        {"date": (NOW - timedelta(days=28)).date().isoformat(), "value": 10},
        {"date": NOW.date().isoformat(), "value": 10},
    ]
    return {"records": records, "retrieved_at": NOW.isoformat()}, "fixture"


def test_macro_is_registered():
    assert is_registered("macro")


def test_healthy_macro_independent_of_cava(tmp_path):
    from rocket.store import ResearchStore

    result = MacroWorkflow(store=ResearchStore(tmp_path), fetcher=_fetcher).run(now=NOW)
    assert_research_result(result)
    assert result.operational.status is OperationalStatus.HEALTHY
    assert result.status is ResearchStatus.NO_SETUP
    assert result.payload["regime"] == "neutral"
    assert "cava" not in result.payload["scope"].lower() or "no Cava" in result.payload["scope"]
    assert macro_is_usable(result.payload, NOW)
    assert not macro_is_usable(result.payload, NOW + timedelta(hours=7))


def test_missing_factor_fail_closed(tmp_path):
    from rocket.store import ResearchStore

    def fetcher(symbol: str):
        if symbol == "EFFR":
            raise RuntimeError("down")
        return _fetcher(symbol)

    result = MacroWorkflow(store=ResearchStore(tmp_path), fetcher=fetcher).run(now=NOW)
    assert_research_result(result)
    assert result.operational.status is OperationalStatus.PARTIAL
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert not macro_is_usable(result.payload, NOW)


def test_all_factors_present_in_contract():
    assert set(FACTORS) == {"EFFR", "WDTGAL", "RRPONTSYD", "WALCL"}
