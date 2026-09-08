"""Issue #12: each IE assertion names the indispensable missing dimension."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from rocket.models import (
    Evidence,
    EvidenceKind,
    Provenance,
    ProviderHealth,
)
from rocket.models import (
    OperationalStatus as O,
)
from rocket.models import (
    ReasonCode as R,
)
from rocket.models import (
    ResearchStatus as S,
)
from rocket.providers.ism import ISMReport, latest_roundup_url
from rocket.providers.protocols import ProviderResult
from rocket.providers.supadata import Transcript
from rocket.store import ResearchStore
from rocket.workflows.cava import (
    CavaCorroboration,
    CavaWorkflow,
    _topics_for,
    corroborate_claims,
    parse_rss,
    transcript_claims,
)
from rocket.workflows.crypto import CryptoWorkflow
from rocket.workflows.disclosures import DisclosureWorkflow
from rocket.workflows.ism import IsmWorkflow
from rocket.workflows.macro import MacroWorkflow
from rocket.workflows.memecoin import MemecoinWorkflow
from rocket.workflows.options import OptionsWorkflow
from rocket.workflows.portfolio import (
    PortfolioState,
    PortfolioWorkflow,
    PositionState,
    review_positions,
)
from rocket.workflows.shorts import ShortsWorkflow, score_candidate
from rocket.workflows.watch import WatchWorkflow, check_watch
from tests.harness import assert_research_result
from tests.workflows.test_cava import NOW as CAVA_NOW
from tests.workflows.test_cava import RSS, FixtureTranscript
from tests.workflows.test_crypto import NOW as CRYPTO_NOW
from tests.workflows.test_crypto import _cap, _macro, _perp, _rising_4h, candidate, replay
from tests.workflows.test_memecoin import NOW as MEME_NOW
from tests.workflows.test_memecoin import snapshot as meme_snapshot
from tests.workflows.test_options import NOW as OPTION_NOW
from tests.workflows.test_options import snapshot as option_snapshot

NOW = datetime(2026, 9, 8, 15, tzinfo=UTC)
WATCH = {"ticker": "CAT", "condition": "ABOVE", "threshold": 100}


def check(result, status, operational, reason=None):
    assert_research_result(result)
    assert result.status is status
    assert result.operational.status is operational
    assert result.payload["execution_enabled"] is False
    if reason:
        assert reason in {item.code for item in result.reasons}
    if status is S.INSUFFICIENT_EVIDENCE:
        assert result.reasons and all(r.missing for r in result.reasons)
        assert result.to_dict()["presentation"] == {"market_result": False, "silent": True, "diagnostic_only": True}
        assert not result.payload.get("cursor_advanced")
    return result


@pytest.mark.parametrize("watches,prices,previous,status,ops,reason,coverage", [
    ([], {}, {}, S.NO_SETUP, O.HEALTHY, None, "NOT_APPLICABLE"),
    ([{}], {}, {}, S.ERROR, O.ERROR, R.INVALID_INPUT, "INVALID_INPUT"),
    ([{"ticker": "CAT"}], {}, {}, S.ERROR, O.ERROR, R.INVALID_INPUT, "INVALID_INPUT"),
    ([WATCH], {}, {}, S.INSUFFICIENT_EVIDENCE, O.UNAVAILABLE, R.REQUIRED_PROVIDER_UNAVAILABLE, "DATA_UNAVAILABLE"),
    ([WATCH], {"CAT": 99}, {}, S.NO_SETUP, O.HEALTHY, None, "OK"),
    ([WATCH], {"CAT": 101}, {}, S.ACTION_REQUIRED, O.HEALTHY, None, "OK"),
    ([WATCH], {"CAT": 101}, {"CAT": 100}, S.NO_SETUP, O.HEALTHY, None, "OK"),
    ([{**WATCH, "condition": "CROSS_ABOVE"}], {"CAT": 101}, {}, S.NO_SETUP, O.HEALTHY, R.WARMUP_STATE, "WARMUP"),
    ([WATCH, {**WATCH, "ticker": "OTHER"}], {"CAT": 99}, {}, S.NO_SETUP, O.PARTIAL, R.REQUIRED_PROVIDER_UNAVAILABLE, "PARTIAL"),
])
def test_watch_matrix(watches, prices, previous, status, ops, reason, coverage):
    result = check(check_watch(watches, prices, previous_prices=previous, now=NOW), status, ops, reason)
    assert result.payload["coverage_status"] == coverage
    assert result.payload["silent"] == (status is not S.ACTION_REQUIRED)


@pytest.mark.parametrize("override", [
    {"available_at": None}, {"available_at": (NOW + timedelta(seconds=1)).isoformat()},
    {"observation_at": (NOW - timedelta(days=10)).isoformat()},
    {"observation_at": "bad"}, {"source": ""}, {"status": "UNAVAILABLE"},
])
def test_watch_rejects_unusable_quote_without_advancing_baseline(tmp_path, override):
    quote = {"status": "OK", "price": 101, "observation_at": NOW.isoformat(),
             "available_at": NOW.isoformat(), "source": "yahoo", **override}
    store = ResearchStore(tmp_path)
    result = WatchWorkflow(store=store).run([WATCH], prices={"CAT": 101}, quote_evidence={"CAT": quote}, now=NOW)
    check(result, S.INSUFFICIENT_EVIDENCE, O.UNAVAILABLE, R.REQUIRED_PROVIDER_UNAVAILABLE)
    assert store.load_state("watch_last_quotes")["prices"] == {}
    assert not result.evidence


def test_watch_warmup_then_cross_and_rearm(tmp_path):
    workflow = WatchWorkflow(store=ResearchStore(tmp_path))
    rule = {**WATCH, "condition": "CROSS_ABOVE"}
    first = workflow.run([rule], prices={"CAT": 99}, now=NOW)
    check(first, S.NO_SETUP, O.HEALTHY, R.WARMUP_STATE)
    second = workflow.run([rule], prices={"CAT": 101}, now=NOW)
    check(second, S.ACTION_REQUIRED, O.HEALTHY)
    assert not workflow.run([rule], prices={"CAT": 102}, now=NOW).payload["events"]


def test_empty_and_invalid_watch_do_not_fetch():
    def forbidden(*args, **kwargs):
        raise AssertionError("no provider work for empty or malformed configuration")
    workflow = WatchWorkflow(quote_fetcher=forbidden)
    check(workflow.run([], now=NOW), S.NO_SETUP, O.HEALTHY)
    check(workflow.run([{}], now=NOW), S.ERROR, O.ERROR, R.INVALID_INPUT)


def macro_fetch(symbol, *, age=0, history=True, available=NOW):
    latest = NOW - timedelta(days=age)
    rows = [{"date": latest.date().isoformat(), "value": 10}]
    if history:
        rows.insert(0, {"date": (latest - timedelta(days=28)).date().isoformat(), "value": 9})
    return {"records": rows, "retrieved_at": available.isoformat()}, "fixture"


@pytest.mark.parametrize("case,status,ops,reason", [
    ("sufficient", S.NO_SETUP, O.HEALTHY, None),
    ("outage", S.INSUFFICIENT_EVIDENCE, O.UNAVAILABLE, R.REQUIRED_PROVIDER_UNAVAILABLE),
    ("partial", S.INSUFFICIENT_EVIDENCE, O.PARTIAL, R.REQUIRED_PROVIDER_UNAVAILABLE),
    ("short", S.INSUFFICIENT_EVIDENCE, O.PARTIAL, R.REQUIRED_EVIDENCE_MISSING),
    ("stale", S.INSUFFICIENT_EVIDENCE, O.PARTIAL, R.REQUIRED_EVIDENCE_MISSING),
    ("late", S.INSUFFICIENT_EVIDENCE, O.PARTIAL, R.REQUIRED_EVIDENCE_MISSING),
])
def test_macro_matrix(case, status, ops, reason):
    def fetch(symbol):
        if case == "outage" or case == "partial" and symbol == "EFFR":
            raise httpx.ConnectError("offline")
        return macro_fetch(symbol, age=20 if case == "stale" else 0, history=case != "short",
                           available=NOW + timedelta(seconds=1) if case == "late" else NOW)
    result = check(MacroWorkflow(fetcher=fetch).run(now=NOW), status, ops, reason)
    assert len(result.operational.providers) == 4
    if status is S.INSUFFICIENT_EVIDENCE:
        assert result.payload["regime"] == "unknown"
    else:
        assert all(e.availability.value == "ELIGIBLE" for e in result.evidence)


@pytest.mark.parametrize("case", ["none", "stale", "unpublished", "malformed"])
def test_ism_fail_closed_identity(case):
    month = {"stale": "August 2022", "unpublished": "September 2026", "malformed": "Unknown"}.get(case)
    reports = {} if month is None else {kind: ISMReport(kind, month, 54) for kind in ("manufacturing", "services")}
    result = check(IsmWorkflow().run(reports=reports, now=NOW), S.INSUFFICIENT_EVIDENCE, O.UNAVAILABLE)
    assert len(result.reasons[0].missing) == 2
    assert not result.evidence


def test_ism_optional_rankings_and_partial_headline():
    result = check(IsmWorkflow().run(reports={"manufacturing": ISMReport("manufacturing", "August 2026", 54)}, now=NOW), S.NO_SETUP, O.PARTIAL)
    assert len(result.evidence) == 1
    assert result.payload["reports"]["manufacturing"]["industry_rankings_status"] == "UNAVAILABLE"


def test_ism_sitemap_uses_month_chronology():
    prefix = "https://www.ismworld.org/blog/2026/ism-pmi-reports-roundup-"
    urls = [f"{prefix}{m}-2026-services/" for m in ("july", "august", "january")]
    assert latest_roundup_url("".join(f"<loc>{url}</loc>" for url in urls), "services") == urls[1]


@pytest.mark.parametrize("failed,new,status,ops", [
    (0, False, S.NO_SETUP, O.HEALTHY), (0, True, S.ACTION_REQUIRED, O.HEALTHY),
    (1, True, S.ACTION_REQUIRED, O.PARTIAL), (1, False, S.NO_SETUP, O.PARTIAL),
    (2, False, S.INSUFFICIENT_EVIDENCE, O.UNAVAILABLE),
])
def test_disclosure_matrix(tmp_path, failed, new, status, ops):
    health = {name: {"status": "UNAVAILABLE" if i < failed else "OK"} for i, name in enumerate(("congress", "executive"))}
    rows = [{"subject": "Caller", "source_url": "https://official.test/filing.pdf"}] if new else []
    store = ResearchStore(tmp_path)
    result = check(DisclosureWorkflow(store=store).run(executive_records=rows, provider_status=health, now=NOW), status, ops)
    assert result.payload["disclosure_is_not_a_buy_signal"]
    if status is S.INSUFFICIENT_EVIDENCE:
        assert store.load_state("disclosures_seen") is None
    elif new:
        assert result.payload["records"][0]["transaction_date"] is None
        assert result.to_dict()["presentation"]["market_result"]


def cava_evidence(topic="rates", **overrides):
    return Evidence(source="fred:DFF", reference=f"cava-{topic}", claim="Observed source value",
                    kind=EvidenceKind.FACT, event_time=CAVA_NOW, available_at=CAVA_NOW,
                    decision_time=CAVA_NOW, provenance=Provenance.PROVIDER_RESULT,
                    metadata={"topic": topic}, **overrides)


@pytest.mark.parametrize("case,status,ops", [
    ("sufficient", S.SETUP_FOUND, O.HEALTHY), ("unsupported_extra", S.SETUP_FOUND, O.HEALTHY),
    ("optional_warning", S.SETUP_FOUND, O.HEALTHY),
    ("missing", S.INSUFFICIENT_EVIDENCE, O.HEALTHY),
    ("contradiction", S.INSUFFICIENT_EVIDENCE, O.HEALTHY),
    ("provider", S.INSUFFICIENT_EVIDENCE, O.PARTIAL),
    ("late", S.INSUFFICIENT_EVIDENCE, O.HEALTHY),
    ("stale", S.INSUFFICIENT_EVIDENCE, O.HEALTHY),
    ("provenance", S.INSUFFICIENT_EVIDENCE, O.HEALTHY),
])
def test_cava_corroboration_matrix(tmp_path, case, status, ops):
    text = "Las tasas de la Fed importan." + (" El oro podría subir." if case == "unsupported_extra" else "")
    transcript = Transcript(text, "es", "supadata", CAVA_NOW)
    ev = cava_evidence()
    if case == "late": ev = replace(ev, available_at=CAVA_NOW + timedelta(seconds=1))
    if case == "stale": ev = replace(ev, event_time=CAVA_NOW - timedelta(days=10))
    if case == "provenance": ev = replace(ev, provenance=Provenance.UNKNOWN)
    corroboration = CavaCorroboration(
        evidence=() if case in {"missing", "provider"} else (ev,),
        warnings=("optional enrichment unavailable",) if case == "optional_warning" else (),
        contradictions=({"topic": "rates"},) if case == "contradiction" else (),
        providers=(ProviderHealth("fred:DFF", O.UNAVAILABLE, failure_kind="ConnectError"),) if case == "provider" else (),
    )
    store = ResearchStore(tmp_path)
    result = check(CavaWorkflow(store=store).run(rss_xml=RSS, transcript_provider=FixtureTranscript(transcript),
                   corroborate=lambda *args: corroboration, now=CAVA_NOW), status, ops)
    assert bool(store.load_state("cava_cursor")) == (status is S.SETUP_FOUND)
    if case == "unsupported_extra":
        assert result.payload["excluded_commentary_topics"] == ["gold"]
        assert "forecasts" in result.payload["validation_scope"]


def test_cava_word_boundaries_and_full_transcript():
    assert _topics_for("El panorama es favorable para nosotros, de otro tipo.") == []
    text = "Saludos. " * 90 + "La inflación importa."
    claims = transcript_claims(parse_rss(RSS)[0], Transcript(text, "es", "supadata", CAVA_NOW), CAVA_NOW)
    assert len(claims) == 91
    assert _topics_for(claims[-1].claim) == ["inflation"]


def test_cava_real_conversion_maps_claims_and_provider_attempts():
    claims = transcript_claims(parse_rss(RSS)[0], Transcript("La inflación importa.", "es", "supadata", CAVA_NOW), CAVA_NOW)
    result = corroborate_claims(claims, CAVA_NOW, series_fetcher=lambda symbol: {
        "records": [{"date": "2026-08-01", "value": 300}, {"date": "2026-09-01", "value": 301}],
        "retrieved_at": CAVA_NOW.isoformat()})
    assert result.evidence[0].metadata["claim_references"] == [claims[0].reference]
    assert result.evidence[0].availability.value == "ELIGIBLE"
    assert result.providers[0].status is O.HEALTHY


@pytest.mark.parametrize("case", ["empty", "missing", "stale", "late", "unknown_source"])
def test_shorts_insufficiency_reasons(case):
    row = {"ticker": "AAPL", "source": "fixture", "event_time": NOW.isoformat(), "available_at": NOW.isoformat(),
           "required_factors": ["company_fundamentals", "technical_breakdown"], "technical_breakdown": True}
    if case == "stale": row["event_time"] = (NOW - timedelta(days=10)).isoformat()
    if case == "late": row["available_at"] = (NOW + timedelta(seconds=1)).isoformat()
    if case == "unknown_source": row.pop("source")
    result = check(ShortsWorkflow().scan([] if case == "empty" else [row], now=NOW), S.INSUFFICIENT_EVIDENCE, O.HEALTHY)
    assert result.reasons[0].code is (R.CALLER_STATE_MISSING if case == "empty" else R.REQUIRED_EVIDENCE_MISSING)


def test_shorts_optional_factors_remain_unknown_and_not_required():
    row = {"ticker": "AAPL", "macro_regime": "bearish", "technical_breakdown": True, "company_fundamentals": True}
    scored = score_candidate(row)
    assert scored["selected"]
    assert scored["factor_states"]["earnings_revision_deterioration"] == "UNKNOWN"
    result = ShortsWorkflow().scan([{**row, "source": "fixture", "event_time": NOW.isoformat(), "available_at": NOW.isoformat()}], now=NOW)
    check(result, S.SETUP_FOUND, O.HEALTHY)


@pytest.mark.parametrize("case", ["empty", "missing", "stale", "late", "malformed", "sufficient"])
def test_options_explicit_scientific_vs_input_gaps(case):
    row = option_snapshot()
    if case == "missing": row["implied_volatility"] = None
    if case == "stale": row["event_time"] = (OPTION_NOW - timedelta(days=2)).isoformat()
    if case == "late": row["available_at"] = (OPTION_NOW + timedelta(seconds=1)).isoformat()
    if case == "malformed": row["event_time"] = "bad"
    result = check(OptionsWorkflow().scan("crypto", [] if case == "empty" else [row], now=OPTION_NOW), S.INSUFFICIENT_EVIDENCE, O.HEALTHY)
    reason = R.CALLER_STATE_MISSING if case == "empty" else R.STRATEGY_UNVALIDATED if case == "sufficient" else R.REQUIRED_EVIDENCE_MISSING
    assert result.reasons[0].code is reason
    assert result.payload["eligible_inputs"] == (1 if case == "sufficient" else 0)


@pytest.mark.parametrize("case", ["empty", "missing", "identity", "late", "malformed", "sufficient"])
def test_memecoin_input_vs_strategy_gaps(case):
    row = meme_snapshot()
    if case == "missing": row["available_at"] = None
    if case == "identity": row["contract_address"] = "0x0"
    if case == "late": row["available_at"] = (MEME_NOW + timedelta(seconds=1)).isoformat()
    if case == "malformed": row["decision_time"] = "bad"
    result = check(MemecoinWorkflow().scan([] if case == "empty" else [row], now=MEME_NOW), S.INSUFFICIENT_EVIDENCE, O.HEALTHY)
    assert result.reasons[0].code is (R.CALLER_STATE_MISSING if case == "empty" else R.STRATEGY_UNVALIDATED if case == "sufficient" else R.REQUIRED_EVIDENCE_MISSING)
    assert bool(result.payload["selected"]) == (case == "sufficient")


def test_crypto_optional_cot_does_not_turn_completed_rejection_into_ie():
    result = CryptoWorkflow().scan_payload(replay(candidate(setup_valid=False)), macro_context=_macro(), cot_regime="unknown")
    check(result, S.NO_SETUP, O.HEALTHY)
    assert result.warnings  # Warnings are diagnostic, never a substitute for required gates.


def test_crypto_macro_is_only_required_for_otherwise_eligible_setup():
    check(CryptoWorkflow().scan_payload(replay(candidate(setup_valid=False))), S.NO_SETUP, O.HEALTHY)
    result = check(CryptoWorkflow().scan_payload(replay(candidate())), S.INSUFFICIENT_EVIDENCE, O.HEALTHY)
    assert "macro" in result.reasons[0].missing[0]


def test_crypto_scans_beyond_old_25_market_cap():
    names = [f"C{i}" for i in range(30)]
    universe = ProviderResult(O.HEALTHY, tuple(_cap(n, n.lower(), i + 1) for i, n in enumerate(names)))
    perps = ProviderResult(O.HEALTHY, tuple(_perp(n) for n in names))
    result = CryptoWorkflow().scan_live(universe=universe, perps=perps, candles={n: _rising_4h() for n in names},
                                       macro_context=_macro(), cot_regime="neutral", now=CRYPTO_NOW)
    check(result, S.SETUP_FOUND, O.HEALTHY)
    assert len(result.payload["final_candidates"]) == 30


def test_portfolio_missing_state_is_not_market_result():
    check(review_positions(PortfolioState(), now=NOW), S.INSUFFICIENT_EVIDENCE, O.HEALTHY, R.CALLER_STATE_MISSING)


def test_portfolio_acquires_for_supplied_positions_without_owning_book():
    calls = []
    def fetch(tickers, **kwargs):
        calls.append(tickers)
        return {"CAT": {"technical_condition": "healthy", "market_state": {
            "current_price": 100, "as_of": NOW.isoformat(), "available_at": NOW.isoformat(), "source": "fixture"}}}
    state = PortfolioState(positions=(PositionState("CAT", thesis="Caller thesis", quantity=2),))
    result = PortfolioWorkflow(market_fetcher=fetch).run(state, now=NOW)
    check(result, S.NO_SETUP, O.HEALTHY)
    assert calls == [["CAT"]]
    assert result.payload["positions"][0]["action"] == "HOLD"  # Macro is optional.
    assert state.positions[0].quantity == 2
    assert state.positions[0].thesis == "Caller thesis"


def test_portfolio_provider_outage_has_typed_gap():
    def fetch(tickers, **kwargs):
        return {"CAT": {"provider_attempts": [{"name": "quote:CAT", "status": "UNAVAILABLE"}]}}
    result = PortfolioWorkflow(market_fetcher=fetch).run(PortfolioState(positions=(PositionState("CAT", thesis="x"),)), now=NOW)
    check(result, S.INSUFFICIENT_EVIDENCE, O.UNAVAILABLE, R.REQUIRED_PROVIDER_UNAVAILABLE)


@pytest.mark.parametrize("override", [{"available_at": None}, {"available_at": (NOW + timedelta(seconds=1)).isoformat()}, {"source": ""}])
def test_portfolio_invalid_pit_cannot_hold(override):
    state = PortfolioState(positions=(PositionState("CAT", thesis="x"),))
    result = review_positions(state, {"CAT": {"technical_condition": "healthy", "market_state": {
        "current_price": 100, "as_of": NOW.isoformat(), "available_at": NOW.isoformat(), "source": "fixture", **override}}}, now=NOW)
    assert result.payload["positions"][0]["action"] == "REVIEW_REQUIRED"
    assert "price_missing_stale_or_invalid" in result.payload["positions"][0]["reasons"]


def test_macro_date_only_freshness_includes_last_allowed_calendar_day():
    def fetch(symbol):
        return macro_fetch(symbol, age=5)
    result = check(MacroWorkflow(fetcher=fetch).run(now=NOW), S.NO_SETUP, O.HEALTHY)
    from rocket.workflows.macro import macro_is_usable
    assert macro_is_usable(result.payload, NOW)
    assert result.payload["factors"]["EFFR"]["max_observation_age_days"] == 5
    # One day older remains insufficient, not an expanded freshness threshold.
    check(MacroWorkflow(fetcher=lambda symbol: macro_fetch(symbol, age=6)).run(now=NOW), S.INSUFFICIENT_EVIDENCE, O.PARTIAL)


def test_short_required_dimensions_cannot_be_disabled_by_caller():
    result = score_candidate({"ticker": "CAT", "required_factors": [], "macro_regime": "bearish",
                              "sector_weakness": True, "positioning_crowding": True})
    assert not result["selected"]
    assert set(result["missing_required_factors"]) == {"company_fundamentals", "technical_breakdown"}


def test_cava_stale_backlog_is_outside_overlay_not_a_failed_research_attempt(tmp_path):
    provider = FixtureTranscript(error="must not be used")
    result = check(CavaWorkflow(store=ResearchStore(tmp_path)).run(rss_xml=RSS, transcript_provider=provider,
                   now=CAVA_NOW + timedelta(days=5)), S.NO_SETUP, O.HEALTHY)
    assert result.payload["outside_overlay_window"] == 2
    assert not provider.calls


def test_cava_missing_source_availability_is_not_fabricated():
    claims = transcript_claims(parse_rss(RSS)[0], Transcript("La inflación importa.", "es", "supadata", CAVA_NOW), CAVA_NOW)
    result = corroborate_claims(claims, CAVA_NOW, series_fetcher=lambda symbol: {"records": [{"date": "2026-09-01", "value": 300}]})
    assert not result.evidence
    assert result.providers[0].status is O.UNAVAILABLE


def test_research_reason_invariant_and_legacy_roundtrip():
    from rocket.models import OperationalReport, ResearchResult
    raw = ResearchResult(workflow="test", status=S.INSUFFICIENT_EVIDENCE,
                         operational=OperationalReport(O.HEALTHY), decision_time=NOW, started_at=NOW)
    with pytest.raises(ValueError, match="machine-readable"):
        raw.validate()
    legacy = {"schema_version": 1, "workflow": "test", "status": "INSUFFICIENT_EVIDENCE",
              "operational": {"status": "HEALTHY"}, "decision_time": NOW.isoformat(), "started_at": NOW.isoformat()}
    restored = ResearchResult.from_dict(legacy)
    assert restored.reasons[0].code is R.LEGACY_UNCLASSIFIED
    assert restored.to_dict()["presentation"]["diagnostic_only"]


def test_ism_rankings_are_independent_evidence():
    from rocket.providers.ism import ISMIndustryRanking
    report = ISMReport("manufacturing", "August 2026", None,
                       expanding=[ISMIndustryRanking("primary metals", "expanding", 1)])
    result = check(IsmWorkflow().run(reports={"manufacturing": report}, now=NOW), S.NO_SETUP, O.PARTIAL)
    assert result.evidence[0].reference == "ism-manufacturing-rankings"
    assert result.payload["reports"]["manufacturing"]["headline_status"] == "UNAVAILABLE"


@pytest.mark.parametrize("source_time", [None, (CRYPTO_NOW + timedelta(seconds=1)).isoformat()])
def test_crypto_universe_pit_required_even_when_candidate_is_eligible(source_time):
    payload = replay(candidate())
    payload["observations"][0]["source_timestamp"] = source_time
    result = check(CryptoWorkflow().scan_payload(payload, macro_context=_macro()), S.INSUFFICIENT_EVIDENCE, O.HEALTHY)
    assert not result.payload["final_candidates"]
    assert result.payload["funnel"]["invalid_observations"] == 1
