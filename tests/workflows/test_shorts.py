from datetime import UTC, datetime

from rocket.models import ResearchStatus
from rocket.providers.shorts import acquire_short_snapshot
from rocket.workflows.shorts import ShortsWorkflow, score_candidate, score_ism_short_candidate
from tests.harness import assert_research_result, is_registered

NOW = datetime(2026, 9, 4, 15, tzinfo=UTC)


def test_shorts_registered():
    assert is_registered("shorts")


def test_company_fundamentals_counts_as_non_macro_factor():
    row = score_candidate(
        {
            "ticker": "AAPL",
            "macro_regime": "risk_off",
            "technical_breakdown": True,
            "company_fundamentals": True,
            "sector_weakness": False,
        }
    )
    assert row["factors"]["company_fundamentals"] is True
    assert row["factor_states"]["company_fundamentals"] == "OBSERVED"
    assert row["selected"] is True


def test_bearish_macro_alone_cannot_select():
    row = score_candidate({"ticker": "AAPL", "macro_regime": "bearish", "required_factors": ["catalyst"]})
    assert row["selected"] is False
    assert row["rejection_reason"] in {"insufficient_evidence", "macro_only", "insufficient_factors"}


def test_missing_required_factor_is_unknown_not_false():
    row = score_candidate({"ticker": "AAPL", "required_factors": ["catalyst"], "catalyst": None})
    assert row["factor_states"]["catalyst"] == "UNKNOWN"
    assert row["selected"] is False
    assert row["rejection_reason"] == "insufficient_evidence"


def test_ism_simple_short_gate_uses_ism_yahoo_and_fmp_inputs():
    row = score_ism_short_candidate(
        {
            "ticker": "WY",
            "candidate_sources": [{"direction": "short", "thesis": "ISM wood products is contracting."}],
            "technical_breakdown": True,
            "company_fundamentals": True,
            "valuation_support": None,
        }
    )
    assert row["selected"] is True
    assert row["strategy"] == "ism_simple"
    assert row["factor_count"] == 3


def test_ism_simple_short_gate_keeps_rejection_reason():
    row = score_ism_short_candidate(
        {
            "ticker": "DOW",
            "candidate_sources": [{"direction": "short"}],
            "technical_breakdown": False,
            "company_fundamentals": True,
        }
    )
    assert row["selected"] is False
    assert row["rejection_reason"] == "technical_breakdown_missing"


def test_ism_simple_short_gate_does_not_short_cheap_fundamentals():
    row = score_ism_short_candidate(
        {
            "ticker": "JPM",
            "candidate_sources": [{"direction": "short"}],
            "technical_breakdown": True,
            "company_fundamentals": True,
            "valuation_support": True,
        }
    )
    assert row["selected"] is False
    assert row["rejection_reason"] == "valuation_support"


def test_ism_simple_live_scan_does_not_require_generic_factors(tmp_path):
    from rocket.candidates import persist_candidates
    from rocket.store import ResearchStore

    store = ResearchStore(tmp_path)
    persist_candidates(
        store,
        "ism",
        [{"ticker": "WY", "direction": "short", "thesis": "ISM wood products is contracting."}],
        now=NOW,
    )

    def fetch(**kwargs):
        return [{
            "ticker": "WY",
            "source": "Yahoo Finance chart API",
            "event_time": NOW.isoformat(),
            "available_at": NOW.isoformat(),
            "acquisition_mode": "LIVE",
            "provider_health": "HEALTHY",
            "technical_breakdown": True,
            "company_fundamentals": True,
            "valuation_support": None,
        }]

    result = ShortsWorkflow(store=store).scan_live(snapshot_fetcher=fetch, now=NOW)
    assert result.status is ResearchStatus.SETUP_FOUND
    assert result.payload["strategy"] == "ism_simple"
    assert result.payload["final_candidates"][0]["asset"] == "WY"


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
