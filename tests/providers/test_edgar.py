"""Recorded companyfacts; all acquisition uses MockTransport, never live SEC."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from rocket.models import OperationalStatus as O
from rocket.providers.edgar import SECEDGAR, apply_price_valuation, parse_companyfacts
from rocket.providers.fmp import FMPClient
from rocket.providers.fundamentals import fundamentals_row
from rocket.providers.protocols import ProviderResult
from rocket.providers.shorts import acquire_short_snapshot
from rocket.workflows.shorts import score_ism_short_candidate

NOW = datetime(2026, 10, 1, 15, tzinfo=UTC)
FIXTURES = Path(__file__).parents[1] / "fixtures/fundamentals/edgar"


def fixture(name):
    return json.loads((FIXTURES / (name + ".json")).read_text())


def test_recorded_cat_reported_eps_revenue_income_and_units():
    row = parse_companyfacts(fixture("cat"), now=NOW)
    assert row["eps_latest_quarter"] == 7.77
    assert row["eps_ttm"] == pytest.approx(23.22)  # FY 18.81 + H1 13.23 - prior H1 8.82
    assert row["eps_growth"] == pytest.approx(0.18228105906313635)
    assert row["eps_accounting"] == "GAAP"
    assert row["eps_window"] == "TTM"
    assert row["eps_quarter_yoy_growth"] == pytest.approx((7.77 - 4.62) / 4.62)
    assert row["metrics"]["eps"]["unit"] == "USD/shares"
    assert row["revenue"]["ttm"] == 74_729_000_000
    assert row["revenue"]["unit"] == "USD"
    assert row["net_income"]["ttm_yoy_growth"] is not None
    assert row["shares_outstanding"] == 459_674_889
    q4 = next(r for r in row["periods"] if r["end"] == "2025-12-31")
    assert q4["derived"] is True
    assert q4["value"] == pytest.approx(18.81 - 13.69)


def test_bank_revenue_tag_and_unknown_custom_only_revenue():
    data = fixture("jpm")
    row = parse_companyfacts(data, now=NOW)
    assert row["eps_ttm"] == pytest.approx(23.34)
    assert row["revenue"]["tag"] == "RevenuesNetOfInterestExpense"
    assert row["net_income"]["ttm"] == 65_067_000_000
    data["facts"]["us-gaap"].pop("RevenuesNetOfInterestExpense")
    data["facts"]["us-gaap"].pop("Revenues")
    row = parse_companyfacts(data, now=NOW)
    assert row["revenue"] is None
    assert row["metric_states"]["revenue"] == "UNKNOWN"
    assert row["eps_growth"] is not None


def test_june_fiscal_year_q4_and_reported_annual_ttm():
    row = parse_companyfacts(fixture("msft"), now=NOW)
    assert row["eps_ttm"] == 17.95
    assert row["eps_growth"] == pytest.approx((17.95 - 13.64) / 13.64)
    assert row["periods"][-1]["start"] == "2026-04-01"
    assert row["periods"][-1]["value"] == pytest.approx(17.95 - 13.14)
    assert row["periods"][-1]["derived"] is True


def test_wmt_partial_recording_does_not_invent_prior_quarters():
    row = parse_companyfacts(fixture("wmt"), now=NOW)
    assert row["eps_latest_quarter"] == 0.8
    assert row["periods"][-1]["start"] == "2026-05-01"
    assert row["eps_ttm"] is None
    assert row["eps_growth"] is None
    assert row["company_fundamentals"] is None


def test_restatements_duplicates_and_future_filings():
    data = fixture("cat")
    facts = data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"]
    raw = next(r for r in facts if r.get("start") == "2026-04-01" and r["end"] == "2026-06-30")
    facts.extend(
        [
            {**raw, "val": 6, "filed": "2026-09-15", "form": "10-Q/A"},
            {**raw, "val": 999, "filed": "2026-12-01"},
            {**raw, "val": 888, "filed": "2026-01-01"},
        ]
    )
    assert parse_companyfacts(data, now=NOW)["eps_latest_quarter"] == 6
    # Comparative facts' fy/fp describe the containing filing, not the period.
    for r in facts:
        r.update(fy=2099, fp="FY")
    assert parse_companyfacts(data, now=NOW)["eps_latest_quarter"] == 6


def test_basic_eps_fallback_wrong_units_and_stale_evidence():
    data = fixture("cat")
    gaap = data["facts"]["us-gaap"]
    gaap["EarningsPerShareBasic"] = gaap.pop("EarningsPerShareDiluted")
    row = parse_companyfacts(data, now=NOW)
    assert row["eps_growth"] is not None
    assert row["metrics"]["eps"]["tag"] == "EarningsPerShareBasic"
    gaap["EarningsPerShareBasic"]["units"]["EUR/shares"] = gaap["EarningsPerShareBasic"][
        "units"
    ].pop("USD/shares")
    assert parse_companyfacts(data, now=NOW)["eps_growth"] is None
    assert parse_companyfacts(fixture("cat"), now=NOW + timedelta(days=400))["eps_growth"] is None


def test_quarter_growth_fallback_no_prior_ttm_and_zero_prior():
    data = fixture("cat")
    units = data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]
    units["USD/shares"] = [
        r for r in units["USD/shares"] if r.get("start") in {"2025-04-01", "2026-04-01"}
    ]
    row = parse_companyfacts(data, now=NOW)
    assert row["eps_growth"] == row["eps_quarter_yoy_growth"]
    assert "latest fiscal quarter" in row["eps_growth_basis"]
    assert row["eps_accounting"] == "GAAP"
    assert row["eps_window"] == "QUARTER"
    for r in units["USD/shares"]:
        if r["start"] == "2025-04-01":
            r["val"] = 0
    assert parse_companyfacts(data, now=NOW)["eps_growth"] is None


def handler_for(calls, *, code=200):
    def handler(req):
        calls.append(req)
        assert "rocket" in req.headers["User-Agent"].lower()
        if req.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json=fixture("company_tickers"))
        if code != 200:
            return httpx.Response(code)
        name = {
            "0000018230": "cat",
            "0000019617": "jpm",
            "0000104169": "wmt",
            "0000789019": "msft",
        }[req.url.path[-15:-5]]
        return httpx.Response(200, json=fixture(name))

    return handler


def test_cache_daily_cik_padding_user_agent_and_safe_payload(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setenv("ROCKET_SEC_USER_AGENT", "rocket research contact@example.test")
    with httpx.Client(transport=httpx.MockTransport(handler_for(calls))) as http:
        edgar = SECEDGAR(state_dir=tmp_path, http=http)
        first = edgar.fetch("cat", now=NOW)
        again = edgar.fetch("CAT", now=NOW + timedelta(hours=1))
        assert len(calls) == 2
        assert first.records[0]["retrieved_at"] == again.records[0]["retrieved_at"]
        assert all(
            a["retrieved_at"] and a["failure_kind"] is None
            for a in first.records[0]["provider_attempts"]
        )
        assert first.records[0]["cik"] == "0000018230"
        edgar.fetch("JPM", now=NOW)
        assert len(calls) == 3  # Shared ticker map, distinct companyfacts.
        edgar.fetch("CAT", now=NOW + timedelta(days=1))
        assert len(calls) == 5
    assert (tmp_path / "cache/sec-edgar/company_tickers.json").exists()
    assert "contact@example.test" not in str(first)
    assert (
        "contact@example.test"
        not in (tmp_path / "cache/sec-edgar/company_tickers.json").read_text()
    )


@pytest.mark.parametrize(
    "code,kind", [(429, "RateLimit"), (403, "Entitlement"), (404, "NotFound"), (500, "HardError")]
)
def test_sec_failure_classification_and_cached_failures(tmp_path, code, kind):
    calls = []
    with httpx.Client(transport=httpx.MockTransport(handler_for(calls, code=code))) as http:
        edgar = SECEDGAR(state_dir=tmp_path, http=http)
        result = edgar.fetch("CAT", now=NOW)
        assert result.failure_kind == kind
        assert result.extras["provider_attempts"][-1]["failure_kind"] == kind
        edgar.fetch("CAT", now=NOW)
        assert len(calls) == 2


def test_sec_unknown_ticker_never_fetches_facts(tmp_path):
    calls = []
    with httpx.Client(transport=httpx.MockTransport(handler_for(calls))) as http:
        result = SECEDGAR(state_dir=tmp_path, http=http).fetch("NO-SUCH-TICKER", now=NOW)
    assert result.failure_kind == "NotFound"
    assert len(calls) == 1
    assert result.extras["provider_attempts"][0]["retrieved_at"]


def test_fmp_429_falls_through_to_sec_once_and_mixed_misses(tmp_path):
    calls, fmp_calls = [], []

    def handler(req):
        if req.url.host == "financialmodelingprep.com":
            fmp_calls.append(req)
            return httpx.Response(429, json={"Error Message": "Limit Reach SECRET"})
        return handler_for(calls)(req)

    massive = Mock()
    massive.fetch.return_value = ProviderResult(
        O.UNAVAILABLE, failure_kind="Entitlement", source="massive"
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        edgar = SECEDGAR(state_dir=tmp_path, http=http)
        # Pin observed fixtures to their recorded date even if the test runs later.
        pinned = Mock()
        pinned.fetch.side_effect = lambda symbol: edgar.fetch(symbol, now=NOW)
        fmp = FMPClient(api_key="SECRET", http=http)
        rows = {
            s: fundamentals_row(s, fmp=fmp, edgar=pinned, massive=massive, price=400)
            for s in ("CAT", "JPM", "WMT", "MISSING")
        }
    assert len(fmp_calls) == 1
    for symbol in ("CAT", "JPM"):
        row = rows[symbol]
        assert row["fundamentals_source"] == "sec.edgar"
        assert row["eps_growth"] is not None
        assert row["pe_ttm"] > 0
        assert row["field_provenance"]["pe_ttm"] == "sec.edgar+yahoo"
        assert row["provider_attempts"][0]["failure_kind"] == "RateLimit"
    assert rows["WMT"]["eps_latest_quarter"] == 0.8  # Partial fields survive exhaustion.
    assert rows["WMT"]["company_fundamentals"] is None
    assert rows["MISSING"]["company_fundamentals"] is None
    assert [c.args[0] for c in massive.fetch.call_args_list] == ["WMT", "MISSING"]
    assert "SECRET" not in json.dumps(rows)


def test_valid_fmp_fields_survive_sec_recovery_and_false_stops_fallback(tmp_path):
    calls = []
    fmp, massive = Mock(), Mock()
    fmp.fundamentals.return_value = ProviderResult(
        O.PARTIAL, ({"pe_ttm": 12, "valuation_support": True},), NOW, source="fmp"
    )
    with httpx.Client(transport=httpx.MockTransport(handler_for(calls))) as http:
        adapter = SECEDGAR(state_dir=tmp_path, http=http)
        edgar = Mock()
        edgar.fetch.side_effect = lambda s: adapter.fetch(s, now=NOW)
        row = fundamentals_row("CAT", fmp=fmp, edgar=edgar, massive=massive, price=400)
        assert row["field_provenance"]["pe_ttm"] == "fmp"
        assert row["valuation_support"] is True
        assert row["fundamentals_source"] == "sec.edgar"
        fmp.fundamentals.return_value = ProviderResult(
            O.HEALTHY, ({"company_fundamentals": False, "eps_growth": 0.1},), NOW, source="fmp"
        )
        row = fundamentals_row("CAT", fmp=fmp, edgar=edgar, massive=massive)
        assert row["fundamentals_source"] == "sec.edgar"
        assert row["eps_accounting"] == "GAAP"
        assert row["eps_window"] == "TTM"
        assert row["eps_provider_disagreement"]["flagged"] is False
        assert edgar.fetch.call_count == 2
        massive.fetch.assert_not_called()


def test_price_valuation_and_unchanged_short_gates(tmp_path, monkeypatch):
    data = fixture("cat")
    # A controlled perturbation of a recording to exercise the bearish gate.
    for r in data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"]:
        if r.get("start", "").startswith("2026"):
            r["val"] /= 4
    row = parse_companyfacts(data, now=NOW)
    row.update(fundamentals_source="sec.edgar", field_provenance={"eps_growth": "sec.edgar"})
    monkeypatch.setattr(
        "rocket.providers.shorts._closes", lambda s, c: ([500.0] * 21 + [400.0], NOW.isoformat())
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: pytest.fail("unexpected network"))
    ) as http:
        snapshot = acquire_short_snapshot(
            universe={"CAT": None}, now=NOW, http=http, fundamentals=lambda s: copy.deepcopy(row)
        )[0]
    snapshot["candidate_sources"] = [{"direction": "short"}]
    assert snapshot["eps_growth"] < 0
    assert snapshot["pe_ttm"] > 15
    assert score_ism_short_candidate(snapshot)["selected"] is True
    for attempt in snapshot["provider_attempts"]:
        assert attempt["retrieved_at"]
        assert attempt["failure_kind"] is None
    snapshot.update(apply_price_valuation({**row, "pe_ttm": None}, 50))
    assert score_ism_short_candidate(snapshot)["rejection_reason"] == "valuation_support"
    for value in (None, 0, -1, float("nan")):
        assert apply_price_valuation({"eps_ttm": value}, 50).get("valuation_support") is None
    snapshot["valuation_support"] = False
    snapshot["technical_breakdown"] = False
    assert score_ism_short_candidate(snapshot)["rejection_reason"] == "technical_breakdown_missing"


def test_healthy_yahoo_quote_attempt_has_null_failure(monkeypatch):
    from rocket.providers.portfolio import acquire_position_evidence

    monkeypatch.setattr(
        "rocket.providers.portfolio.acquire_quotes",
        lambda *a, **kw: {
            "CAT": {
                "status": "OK",
                "classification": "PROVIDER_SUPPORTED",
                "price": 400,
                "observation_at": NOW.isoformat(),
                "available_at": NOW.isoformat(),
                "retrieved_at": NOW.isoformat(),
                "source": "Yahoo",
            }
        },
    )
    monkeypatch.setattr(
        "rocket.providers.portfolio.equity_history", lambda *a, **kw: ([400.0] * 22, NOW.isoformat(), 4.0, {})
    )
    with httpx.Client() as http:
        row = acquire_position_evidence(["CAT"], now=NOW, http=http)["CAT"]
    assert row["provider_attempts"][0]["failure_kind"] is None


def test_q4_without_nine_month_facts_and_quarter_gap():
    data = fixture("cat")
    units = data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]
    units["USD/shares"] = [
        r
        for r in units["USD/shares"]
        if not (r.get("start") == "2025-01-01" and r["end"] == "2025-09-30")
    ]
    row = parse_companyfacts(data, now=NOW)
    q4 = next(r for r in row["periods"] if r["end"] == "2025-12-31")
    assert q4["derived"] is True
    assert q4["value"] == pytest.approx(18.81 - 4.2 - 4.62 - 4.88)
    # No annual/YTD bridge and no complete four-quarter window: TTM stays missing.
    units["USD/shares"] = [
        r
        for r in units["USD/shares"]
        if r.get("start") in {"2025-07-01", "2026-01-01", "2026-04-01"}
        and r["end"] in {"2025-09-30", "2026-03-31", "2026-06-30"}
    ]
    assert parse_companyfacts(data, now=NOW)["eps_ttm"] is None


@pytest.mark.parametrize(
    "payload", [{}, {"cik": 999, "facts": {}}, [], {"cik": 18230, "facts": "bad"}]
)
def test_malformed_or_wrong_issuer_is_hard_error(tmp_path, payload):
    def handler(req):
        if req.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json=fixture("company_tickers"))
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        result = SECEDGAR(state_dir=tmp_path, http=http).fetch("CAT", now=NOW)
    assert result.failure_kind == "HardError"
    assert result.extras["provider_attempts"][-1]["failure_kind"] == "HardError"


def test_request_spacing_and_valid_fmp_still_reads_edgar(tmp_path, monkeypatch):
    import rocket.providers.edgar as module

    sleeps = []
    monkeypatch.setattr(module, "_LAST_REQUEST", 10.0)
    monkeypatch.setattr(module.time, "monotonic", lambda: 10.0)
    monkeypatch.setattr(module.time, "sleep", sleeps.append)
    calls = []
    with httpx.Client(transport=httpx.MockTransport(handler_for(calls))) as http:
        SECEDGAR(state_dir=tmp_path, http=http).fetch("CAT", now=NOW)
    assert sleeps == [0.35, 0.35]
    fmp, edgar, massive = Mock(), Mock(), Mock()
    fmp.fundamentals.return_value = ProviderResult(
        O.HEALTHY, ({"company_fundamentals": False, "eps_growth": 0.1,
                     "eps_growth_basis": "reported annual EPS growth",
                     "eps_accounting": "UNSPECIFIED", "eps_window": "ANNUAL"},), NOW, source="fmp"
    )
    edgar.fetch.return_value = ProviderResult(O.UNAVAILABLE, failure_kind="Empty", source="sec.edgar")
    row = fundamentals_row("CAT", fmp=fmp, edgar=edgar, massive=massive)
    assert row["fundamentals_source"] == "fmp"
    assert row["eps_accounting"] == "UNSPECIFIED"
    assert row["eps_window"] == "ANNUAL"
    assert row["eps_provider_disagreement"] is None
    edgar.fetch.assert_called_once()
    massive.fetch.assert_not_called()


def test_fmp_http_200_limit_reach_stops_requests():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json={"Error Message": "Limit Reach SECRET"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = FMPClient(api_key="SECRET", http=http)
        for symbol in ("CAT", "WMT"):
            result = client.fundamentals(symbol)
            assert result.failure_kind == "RateLimit"
            assert "SECRET" not in str(result)
    assert len(calls) == 1
