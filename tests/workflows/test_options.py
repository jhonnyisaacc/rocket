from datetime import UTC, datetime

from rocket.models import ResearchStatus
from rocket.workflows.options import OptionsWorkflow
from tests.harness import assert_research_result, is_registered

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


def snapshot(**overrides):
    row = {
        "underlying": "BTC",
        "available_at": "2026-09-04T11:00:00+00:00",
        "event_time": "2026-09-04T10:55:00+00:00",
        "implied_volatility": 0.48,
        "realized_volatility": 0.35,
        "defined_risk": True,
        "source": "fixture",
    }
    row.update(overrides)
    return row


def test_options_registered():
    assert is_registered("options.scan")


def test_scan_never_auto_validates_and_keeps_domains_separate():
    result = OptionsWorkflow().scan("crypto", [snapshot()], now=NOW)
    assert_research_result(result)
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert result.payload["strategy_state"] == "EXPERIMENTAL"
    assert result.payload["strategy"]["underlyings"] == ["BTC", "ETH"]
    assert result.payload["observations"][0]["iv_rv_spread"] == 0.13


def test_out_of_scope_and_missing_dimensions():
    result = OptionsWorkflow().scan("crypto", [snapshot(underlying="SOL"), snapshot(realized_volatility=None)], now=NOW)
    assert_research_result(result)
    reasons = {item["reason"] for item in result.payload["rejected_inputs"]}
    assert "outside_crypto_scope" in reasons
    assert "missing_dimensions" in reasons


def test_evaluate_is_gross_uncosted_and_not_validated():
    result = OptionsWorkflow().evaluate("crypto", [{"forward_return_pct": 2.0}] * 30, now=NOW)
    assert_research_result(result)
    assert result.payload["cost_basis"] == "GROSS_UNCOSTED"
    assert result.payload["strategy_state"] == "EXPERIMENTAL"
    assert "VALIDATED" in result.warnings[0]
