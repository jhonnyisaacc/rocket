from datetime import UTC, datetime

from rocket.models import ResearchStatus
from rocket.providers.shorts import acquire_short_snapshot
from rocket.workflows.shorts import ShortsWorkflow, score_candidate
from tests.harness import assert_research_result, is_registered

NOW = datetime(2026, 9, 4, 15, tzinfo=UTC)


def test_shorts_registered():
    assert is_registered("shorts")


def test_bearish_macro_alone_cannot_select():
    row = score_candidate({"ticker": "AAPL", "macro_regime": "bearish", "required_factors": ["catalyst"]})
    assert row["selected"] is False
    assert row["rejection_reason"] in {"insufficient_evidence", "macro_only", "insufficient_factors"}


def test_missing_required_factor_is_unknown_not_false():
    row = score_candidate({"ticker": "AAPL", "required_factors": ["catalyst"], "catalyst": None})
    assert row["factor_states"]["catalyst"] == "UNKNOWN"
    assert row["selected"] is False
    assert row["rejection_reason"] == "insufficient_evidence"


def test_scan_no_setup_when_healthy_and_nothing_selected():
    rows = [
        {
            "ticker": "AAPL",
            "available_at": NOW.isoformat(),
            "event_time": NOW.isoformat(),
            "source": "fixture",
            "macro_regime": "neutral",
            "acquisition_mode": "LIVE",
            "provider_health": "HEALTHY",
            "required_factors": ["catalyst"],
        }
    ]
    result = ShortsWorkflow().scan(rows, now=NOW)
    assert_research_result(result)
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert result.payload["final_candidates"] == []
    assert result.payload["rejected_candidates"]


def test_live_snapshot_merges_fmp_factors_without_inventing_catalyst():
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "chart": {
                    "result": [
                        {
                            "indicators": {"quote": [{"close": list(range(80, 110))}]},
                            "meta": {"regularMarketTime": int(NOW.timestamp())},
                        }
                    ]
                }
            }

    class _Client:
        def get(self, *args, **kwargs):
            return _Response()

        def close(self):
            return None

    rows = acquire_short_snapshot(
        now=NOW,
        universe={"AAPL": "XLK"},
        http=_Client(),
        fundamentals=lambda ticker: {
            "company_fundamentals": True,
            "earnings_revision_deterioration": True,
            "valuation_support": False,
            "fundamentals_source": "fmp",
        },
    )
    assert rows[0]["company_fundamentals"] is True
    assert rows[0]["catalyst"] is None
    assert "catalyst" not in rows[0]["required_factors"]
    assert rows[0]["fundamentals_source"] == "fmp"
