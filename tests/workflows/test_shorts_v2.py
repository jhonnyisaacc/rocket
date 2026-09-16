from datetime import UTC, datetime, timedelta

from rocket.models import ResearchStatus
from rocket.providers.estimate_revisions import compare_same_period, revision_30d
from rocket.providers.ism import ISMIndustryRanking, ISMReport
from rocket.providers.ism_universe import (
    build_short_universe,
    select_contracting_industries,
    select_short_discovery,
)
from rocket.providers.short_events import catalyst_record, eligible_catalysts
from rocket.providers.short_quality import (
    breakdown,
    classify_regime,
    failed_retest,
    relative_strength,
    risk_reward,
)
from rocket.providers.short_research_ai import qualitative_contract
from rocket.providers.tokenized_equities import RESEARCH_ELIGIBLE, eligibility, instrument_record
from rocket.store import ResearchStore
from rocket.workflows.ism import IsmWorkflow
from rocket.workflows.shorts import ShortsWorkflow, score_ism_short_candidate, score_shorts_v2

NOW = datetime(2026, 9, 16, 15, tzinfo=UTC)


def test_selects_up_to_three_worst_contracting_industries():
    rows = [
        ISMIndustryRanking("wood products", "contracting", 1),
        ISMIndustryRanking("chemical products", "contracting", 2),
        ISMIndustryRanking("paper products", "contracting", 3),
        ISMIndustryRanking("furniture & related products", "contracting", 4),
    ]
    selected = select_contracting_industries(rows)
    assert [row["industry"] for row in selected] == ["wood products", "chemical products", "paper products"]


def test_fewer_than_three_contracting_industries_are_kept():
    rows = [ISMIndustryRanking("wood products", "contracting", 1)]
    assert [row["industry"] for row in select_contracting_industries(rows)] == ["wood products"]


def test_manufacturing_and_services_stay_distinct():
    reports = {
        "manufacturing": {"worst_industries": [ISMIndustryRanking("wood products", "contracting", 1)]},
        "services": {"worst_industries": [ISMIndustryRanking("construction", "contracting", 1)]},
    }
    selected = select_short_discovery(reports)
    assert selected["manufacturing"][0]["industry"] == "wood products"
    assert selected["services"][0]["industry"] == "construction"


def test_unmapped_ism_industry_is_recorded():
    universe = build_short_universe(
        {"manufacturing": [{"industry": "textile mills", "rank": 1, "trend": "contracting"}]},
        {},
        now=NOW,
    )
    assert universe["seeds"] == []
    assert universe["unmapped"][0]["industry"] == "textile mills"


def test_multiple_companies_per_industry_and_ticker_dedup_across_themes():
    exposures = {
        "machinery": [{"ticker": "CAT", "sector_etf": "XLI", "exposure": "equipment", "source": "issuer", "reviewed_at": "2026-09-08"}],
        "construction": [{"ticker": "CAT", "sector_etf": "XLI", "exposure": "equipment", "source": "issuer", "reviewed_at": "2026-09-08"},
                         {"ticker": "DHI", "sector_etf": "XLY", "exposure": "homebuilding", "source": "issuer", "reviewed_at": "2026-09-16"}],
    }
    universe = build_short_universe(
        {
            "manufacturing": [{"industry": "machinery", "rank": 1, "trend": "contracting"}],
            "services": [{"industry": "construction", "rank": 1, "trend": "contracting"}],
        },
        exposures,
        now=NOW,
    )
    assert {seed["ticker"] for seed in universe["seeds"]} == {"CAT", "DHI"}
    assert len(universe["by_ticker"]["CAT"]) == 2


def test_strict_pit_mappings_exclude_future_reviews():
    exposures = {"wood products": [{"ticker": "WY", "exposure": "wood", "source": "issuer", "reviewed_at": "2026-09-16"}]}
    selected = {"manufacturing": [{"industry": "wood products", "rank": 1, "trend": "contracting"}]}
    assert build_short_universe(selected, exposures, now=datetime(2026, 3, 1, tzinfo=UTC), mapping_mode="strict_pit")["seeds"] == []
    assert build_short_universe(selected, exposures, now=NOW, mapping_mode="strict_pit")["seeds"][0]["ticker"] == "WY"


def test_relative_strength_and_unknown_propagation():
    row = relative_strength([100, 90], [100, 95], [100, 110], window=1)
    assert round(row["relative_vs_sector"], 6) == round((0.9 - 0.95), 6)
    assert row["underperforms_both"] is True
    missing = relative_strength([100, 90], None, [100, 110], window=1)
    assert missing["relative_vs_sector"] is None
    assert missing["state"] == "UNKNOWN"


def test_same_fiscal_period_revisions_and_incompatible_rejection():
    later = {"period": "annual", "date": "2027-12-31", "eps": 1.0, "available_at": NOW.isoformat()}
    earlier = {"period": "annual", "date": "2027-12-31", "eps": 1.2, "available_at": (NOW - timedelta(days=30)).isoformat()}
    same = compare_same_period(later, earlier, metric="eps")
    assert same["state"] == "DETERIORATING"
    other = compare_same_period(later, {**earlier, "date": "2026-12-31"}, metric="eps")
    assert other["state"] == "UNKNOWN"
    assert other["reason"] == "incompatible_fiscal_period"


def test_revision_30d_requires_stored_same_period_history():
    snapshots = [
        {"symbol": "DOW", "period": "annual", "fiscal_date": "2027-12-31", "date": "2027-12-31", "eps": 2.0,
         "available_at": (NOW - timedelta(days=30)).isoformat(), "source": "fixture"},
        {"symbol": "DOW", "period": "annual", "fiscal_date": "2027-12-31", "date": "2027-12-31", "eps": 1.5,
         "available_at": NOW.isoformat(), "source": "fixture"},
    ]
    row = revision_30d(snapshots, "DOW", now=NOW, metric="eps")
    assert row["state"] == "DETERIORATING"
    assert revision_30d([], "DOW", now=NOW)["state"] == "UNKNOWN"


def test_catalyst_requires_evidence_and_pit():
    assert catalyst_record(type="GUIDANCE_CUT", event_time=None, available_at=NOW, source="sec", summary="cut") is None
    row = catalyst_record(type="GUIDANCE_CUT", event_time=NOW, available_at=NOW, source="sec.8-k", summary="guidance reduced")
    late = {**row, "available_at": (NOW + timedelta(days=1)).isoformat()}
    assert eligible_catalysts([late], now=NOW) == []
    assert eligible_catalysts([row], now=NOW)[0]["type"] == "GUIDANCE_CUT"


def test_breakdown_and_failed_retest():
    steady = [10] * 20 + [9]
    assert breakdown(steady) is True
    # breakdown at 20 (close 8 < prior low 10), retest at 21 (close 10), fail at last (close 7)
    series = [10] * 20 + [8, 10, 7]
    assert failed_retest(series, retest_window=5)["failed_retest"] is True
    assert failed_retest([10] * 20 + [8, 7], retest_window=5)["failed_retest"] is False


def test_regime_and_risk_reward_unknown():
    spy = [100] * 19 + [90]
    sector = [50] * 19 + [40]
    assert classify_regime(spy, sector)["regime"] == "SHORT_FRIENDLY"
    assert risk_reward(10, 11, 8)["reward_to_risk"] == 2.0
    assert risk_reward(10, 9, 8)["reward_to_risk"] == "UNKNOWN"
    assert risk_reward(10, 11, None)["reward_to_risk"] == "UNKNOWN"


def test_watch_to_triggered_state_machine():
    base = {
        "ticker": "WY",
        "candidate_sources": [{"direction": "short", "industry": "wood products", "rank": 1}],
        "company_fundamentals": True,
        "relative_vs_sector": -0.08,
        "relative_vs_market": -0.11,
        "technical_breakdown": False,
        "failed_retest": False,
        "current_price": 20,
        "invalidation": 22,
        "target": 16,
    }
    watch = score_shorts_v2(base)
    assert watch["state"] == "WATCH"
    assert watch["selected"] is False
    triggered = score_shorts_v2({**base, "technical_breakdown": True})
    assert triggered["state"] == "TRIGGERED"
    armed = score_shorts_v2({**base, "technical_breakdown": True, "failed_retest": False}, require_failed_retest=True)
    assert armed["state"] == "ARMED"
    unknown = score_shorts_v2({**base, "company_fundamentals": None, "relative_vs_sector": None, "relative_vs_market": None})
    assert unknown["state"] == "RESEARCH"
    assert unknown["factor_states"]["company_deterioration"] == "UNKNOWN"


def test_baseline_ism_simple_still_requires_breakdown():
    row = score_ism_short_candidate({
        "ticker": "WY",
        "candidate_sources": [{"direction": "short"}],
        "technical_breakdown": False,
        "company_fundamentals": True,
    })
    assert row["selected"] is False
    assert row["rejection_reason"] == "technical_breakdown_missing"


def test_tokenized_research_vs_execution_and_no_present_inference():
    now = NOW
    current = instrument_record(
        underlying="WY", venue="xstocks", source="xstocks", observed_at=now, available_at=now,
        token_symbol="WYx", instrument_type="tokenized_spot", long_available=True, short_available=True,
    )
    row = eligibility("WY", [current], now=datetime(2026, 1, 15, tzinfo=UTC))
    assert row["research"]["status"] == RESEARCH_ELIGIBLE
    assert row["execution"]["status"] == "UNKNOWN"
    present = eligibility("WY", [current], now=now)
    assert present["execution"]["status"] == "EXECUTION_ELIGIBLE"


def test_v2_scan_watch_is_no_setup_not_selected(tmp_path):
    rows = [{
        "ticker": "WY",
        "source": "fixture",
        "event_time": NOW.isoformat(),
        "available_at": NOW.isoformat(),
        "candidate_sources": [{"direction": "short"}],
        "company_fundamentals": True,
        "relative_vs_sector": -0.06,
        "relative_vs_market": -0.04,
        "technical_breakdown": False,
        "current_price": 20,
        "invalidation": 22,
        "target": 15,
    }]
    result = ShortsWorkflow(store=ResearchStore(tmp_path)).scan(rows, now=NOW, scorer=score_shorts_v2, strategy="shorts_v2")
    assert result.status is ResearchStatus.NO_SETUP
    assert result.payload["watchlist"][0]["state"] == "WATCH"
    assert result.payload["final_candidates"] == []


def test_stale_and_future_rows_still_fail_closed():
    late = {"ticker": "WY", "source": "fixture", "event_time": NOW.isoformat(),
            "available_at": (NOW + timedelta(seconds=1)).isoformat(),
            "candidate_sources": [{"direction": "short"}], "company_fundamentals": True,
            "technical_breakdown": True, "relative_vs_sector": -0.1, "relative_vs_market": -0.1}
    result = ShortsWorkflow().scan([late], now=NOW, scorer=score_shorts_v2, strategy="shorts_v2")
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert result.payload["rejected_candidates"][0]["reason"] == "available_after_decision_time"


def test_ism_short_discovery_uses_top_three_only(tmp_path):
    contracting = [
        ISMIndustryRanking("wood products", "contracting", 1),
        ISMIndustryRanking("chemical products", "contracting", 2),
        ISMIndustryRanking("paper products", "contracting", 3),
        ISMIndustryRanking("furniture & related products", "contracting", 4),
    ]
    exposures = {
        "wood products": [{"ticker": "WY", "exposure": "wood", "source": "issuer"}],
        "chemical products": [{"ticker": "DOW", "exposure": "chem", "source": "issuer"}],
        "paper products": [{"ticker": "IP", "exposure": "paper", "source": "issuer"}],
        "furniture & related products": [{"ticker": "LEG", "exposure": "furniture", "source": "issuer"}],
    }
    result = IsmWorkflow(store=ResearchStore(tmp_path), exposures=exposures,
                         context_fetcher=lambda ts: {}).run(
        reports={"manufacturing": ISMReport("manufacturing", "August 2026", 54.6, [], contracting, "https://official.test")},
        now=NOW,
        research_companies=True,
    )
    shorts = [row["ticker"] for row in result.payload["candidates"] if row["direction"] == "short"]
    assert set(shorts) == {"WY", "DOW", "IP"}
    assert "LEG" not in shorts
    assert [row["industry"] for row in result.payload["short_discovery"]["manufacturing"]] == [
        "wood products", "chemical products", "paper products",
    ]


def test_qualitative_layer_is_not_a_signal():
    contract = qualitative_contract()
    assert "numerical short signal" in contract["must_not"]
    assert contract["backtest_dependent"] is False


def test_daily_bars_reject_session_close_after_decision():
    from rocket.providers.historical_prices import bars_eligible_at

    history = {
        "source": "Yahoo Finance chart API",
        "records": [
            {"date": "2026-09-15", "close": 10, "high": 11, "low": 9},
            {"date": "2026-09-16", "close": 12, "high": 13, "low": 11},
        ],
    }
    rows = bars_eligible_at(history, datetime(2026, 9, 16, 17, tzinfo=UTC))  # 13:00 NY, before close
    assert [row["date"] for row in rows] == ["2026-09-15"]
