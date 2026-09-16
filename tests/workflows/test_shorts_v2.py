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


def test_eight_k_item_semantics_are_not_generic_bearish():
    from rocket.providers.short_events import from_sec_filing, item_semantics

    assert item_semantics("2.02")["type"] == "EARNINGS_EVENT"
    assert item_semantics("2.02")["bearish_by_itself"] is False
    miss = from_sec_filing(
        {"form": "8-K", "filingDate": "2026-09-01", "items": "2.02,9.01", "accessionNumber": "0001", "source": "sec"},
        now=NOW,
    )
    assert miss["type"] == "EARNINGS_EVENT"
    assert miss["direction"] == "UNKNOWN"
    assert miss["counts_for_selection"] is False
    auditor = from_sec_filing(
        {"form": "8-K", "filingDate": "2026-09-01", "items": "4.01", "source": "sec"}, now=NOW,
    )
    assert auditor["type"] == "AUDITOR_CHANGE"
    assert auditor["direction"] == "UNKNOWN"
    restatement = from_sec_filing(
        {"form": "8-K", "filingDate": "2026-09-01", "items": "4.02", "source": "sec"}, now=NOW,
    )
    assert restatement["type"] == "NON_RELIANCE"
    assert restatement["direction"] == "BEARISH"
    assert restatement["counts_for_selection"] is True


def test_bearish_catalyst_requires_bearish_direction():
    from rocket.providers.short_events import bearish_catalysts, catalyst_record

    generic = catalyst_record(
        type="EARNINGS_EVENT", event_time=NOW, available_at=NOW, source="sec", summary="8-K 2.02", direction="UNKNOWN",
    )
    miss = catalyst_record(
        type="EARNINGS_MISS", event_time=NOW, available_at=NOW, source="surprise", summary="EPS missed", direction="BEARISH",
    )
    assert bearish_catalysts([generic, miss], now=NOW) == [miss]
    watch = score_shorts_v2({
        "ticker": "WY",
        "candidate_sources": [{"direction": "short"}],
        "company_fundamentals": True,
        "relative_vs_sector": -0.1,
        "relative_vs_market": -0.1,
        "technical_breakdown": True,
        "catalysts": [generic],
        "current_price": 20,
        "invalidation": 22,
        "target": 16,
        "available_at": NOW.isoformat(),
        "event_time": NOW.isoformat(),
        "source": "fixture",
    }, require_bearish_catalyst=True)
    assert watch["state"] == "WATCH"
    assert watch["rejection_reason"] == "bearish_catalyst_missing"


def test_xstocks_pagination_and_spot_does_not_imply_short():
    import httpx

    from rocket.providers.tokenized_equities import (
        EXECUTION_ELIGIBLE,
        fetch_xstocks_assets,
        parse_kraken_xstock_perps,
        parse_ondo_perps,
    )

    pages = {
        "1": {"nodes": [{"underlyingSymbol": "AAPL", "symbol": "AAPLx", "isTradingHalted": False}],
              "page": {"currentPage": 1, "hasNextPage": True}},
        "2": {"nodes": [{"underlyingSymbol": "MSFT", "symbol": "MSFTx", "isTradingHalted": False}],
              "page": {"currentPage": 2, "hasNextPage": False}},
    }
    calls = []

    def handler(request):
        page = request.url.params.get("page")
        calls.append(page)
        return httpx.Response(200, json=pages[page], request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        records = fetch_xstocks_assets(client, retrieved_at=NOW, page_size=1)
    assert calls == ["1", "2"]
    assert {row["underlying"] for row in records} == {"AAPL", "MSFT"}
    assert all(row["short_available"] is None for row in records)
    spot = eligibility("AAPL", records, now=NOW)
    assert spot["execution"]["status"] == "UNKNOWN"

    perps = parse_kraken_xstock_perps(
        [{"symbol": "PF_AAPLXUSD", "base": "AAPLx", "tradeable": True, "openingDate": "2026-02-06T00:00:00Z"}],
        [{"symbol": "PF_AAPLXUSD", "markPrice": 100, "indexPrice": 99, "fundingRate": 0.001, "vol24h": 10,
          "openInterest": 20, "bid": 99.5, "ask": 100.5, "suspended": False}],
        retrieved_at=NOW,
    )
    assert perps[0]["instrument_type"] == "tokenized_perp"
    assert perps[0]["short_available"] is True
    assert eligibility("AAPL", perps, now=NOW)["execution"]["status"] == EXECUTION_ELIGIBLE
    ondo = parse_ondo_perps({
        "result": [{"market": "AAPL-USD.P", "productType": "perpetual", "baseCurrency": "AAPL",
                    "quoteCurrency": "USDC", "disabled": False, "lastPrice": "100", "indexPrice": "100",
                    "fundingRate": "0.0001", "usdVolume": "1", "openInterestUsd": "2", "bid": "99", "ask": "101"}],
    }, retrieved_at=NOW)
    assert ondo[0]["short_available"] is True


def test_history_target_is_not_full_history_low_and_unknown_stays_unknown():
    from rocket.providers.short_quality import (
        history_target,
        research_entry_price,
        select_downside_target,
    )

    ancient = [1.0] + [50.0] * 200 + [48.0]
    assert history_target(ancient) != 1.0
    assert select_downside_target(ancient)["rule"] != "full_history_low"
    trough = [50.0] * 20 + [40.0, 41.0, 42.0] + [50.0] * 30 + [48.0]
    assert history_target(trough) == 40.0
    assert history_target([10.0] * 30) is None
    assert risk_reward(10, 11, None)["reward_to_risk"] == "UNKNOWN"
    close_entry = research_entry_price(signal_close=10, next_open=11, mode="CLOSE_SIGNAL")
    open_entry = research_entry_price(signal_close=10, next_open=11, mode="NEXT_SESSION_OPEN")
    assert close_entry["entry"] == 10
    assert open_entry["entry"] == 11
    assert research_entry_price(signal_close=10, next_open=None, mode="NEXT_SESSION_OPEN")["entry"] is None


def test_one_ticker_one_trade_with_multi_theme_attribution():
    from rocket.providers.ism_universe import primary_seed

    exposures = {
        "machinery": [{"ticker": "CAT", "sector_etf": "XLI", "exposure": "equipment", "source": "issuer", "reviewed_at": "2026-09-08"}],
        "construction": [{"ticker": "CAT", "sector_etf": "XLI", "exposure": "equipment", "source": "issuer", "reviewed_at": "2026-09-08"}],
    }
    universe = build_short_universe(
        {
            "manufacturing": [{"industry": "machinery", "rank": 1, "trend": "contracting"}],
            "services": [{"industry": "construction", "rank": 1, "trend": "contracting"}],
        },
        exposures,
        now=NOW,
    )
    assert len(universe["seeds"]) == 2
    assert list(universe["by_ticker"]) == ["CAT"]
    seed = primary_seed(universe["by_ticker"]["CAT"])
    assert seed["ticker"] == "CAT"
    assert {row["industry"] for row in universe["by_ticker"]["CAT"]} == {"machinery", "construction"}


def test_live_v2_path_uses_v2_providers_and_persists_estimates(tmp_path):
    from rocket.candidates import persist_candidates
    from rocket.providers.shorts import acquire_short_snapshot_v2

    store = ResearchStore(tmp_path)
    persist_candidates(store, "ism", [{"ticker": "WY", "direction": "short", "thesis": "wood"}], now=NOW)
    called = {"sec": 0, "cat": 0, "est": 0, "tok": 0}

    def market(**kwargs):
        return [{
            "ticker": "WY",
            "source": "Yahoo Finance chart API",
            "event_time": NOW.isoformat(),
            "available_at": NOW.isoformat(),
            "acquisition_mode": "LIVE",
            "provider_health": "HEALTHY",
            "technical_breakdown": True,
            "company_fundamentals": True,
            "relative_vs_sector": -0.1,
            "relative_vs_market": -0.1,
            "current_price": 20,
            "invalidation": 22,
            "target": 16,
            "provider_attempts": [],
        }]

    def sec(ticker, now=None):
        called["sec"] += 1
        return {"company_fundamentals": True, "cash_flow_quality": {"state": "DETERIORATING"}, "provider_attempts": [{"name": "sec.companyfacts", "status": "HEALTHY"}]}

    def cats(ticker, now=None):
        called["cat"] += 1
        return []

    def estimates(ticker, now=None):
        called["est"] += 1
        return [{"period": "annual", "date": "2027-12-31", "epsAvg": 1.2, "revenueAvg": 10, "symbol": ticker}]

    def tokenized():
        called["tok"] += 1
        return []

    rows = acquire_short_snapshot_v2(
        universe={"WY": "XLI"}, now=NOW, store=store, market_fetcher=market,
        sec_fetcher=sec, catalyst_fetcher=cats, estimates_fetcher=estimates, tokenized_fetcher=tokenized,
    )
    assert called == {"sec": 1, "cat": 1, "est": 1, "tok": 1}
    assert rows[0]["acquisition_path"] == "shorts_v2"
    assert rows[0]["snapshots_persisted"] == 1
    assert store.load_state("estimate_snapshots")["snapshots"][0]["symbol"] == "WY"
    result = ShortsWorkflow(store=store).scan_live(
        now=NOW, strategy="shorts_v2",
        snapshot_fetcher=lambda **kwargs: acquire_short_snapshot_v2(
            universe=kwargs["universe"], now=NOW, store=store, market_fetcher=market,
            sec_fetcher=sec, catalyst_fetcher=cats, estimates_fetcher=estimates, tokenized_fetcher=tokenized,
        ),
    )
    assert result.payload["strategy"] == "shorts_v2"


def test_scan_live_shorts_v2_defaults_to_v2_acquisition(monkeypatch, tmp_path):
    from rocket.candidates import persist_candidates
    from rocket.providers import shorts as shorts_provider

    store = ResearchStore(tmp_path)
    persist_candidates(store, "ism", [{"ticker": "WY", "direction": "short", "thesis": "wood"}], now=NOW)
    called = {}

    def fake_v2(**kwargs):
        called["v2"] = True
        called["store"] = kwargs.get("store") is store
        return [{
            "ticker": "WY",
            "source": "Yahoo Finance chart API",
            "event_time": NOW.isoformat(),
            "available_at": NOW.isoformat(),
            "acquisition_mode": "LIVE",
            "provider_health": "HEALTHY",
            "technical_breakdown": True,
            "company_fundamentals": True,
            "relative_vs_sector": -0.08,
            "relative_vs_market": -0.09,
            "current_price": 20,
            "invalidation": 22,
            "target": 15,
            "provider_attempts": [],
        }]

    monkeypatch.setattr(shorts_provider, "acquire_short_snapshot_v2", fake_v2)
    result = ShortsWorkflow(store=store).scan_live(now=NOW, strategy="shorts_v2")
    assert called.get("v2") is True
    assert called.get("store") is True
    assert result.payload["strategy"] == "shorts_v2"
