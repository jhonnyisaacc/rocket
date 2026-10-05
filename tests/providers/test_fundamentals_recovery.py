import json
from datetime import UTC, datetime
from unittest.mock import Mock

import httpx
import pytest

from rocket.models import OperationalStatus as O
from rocket.providers.fmp import FMPClient
from rocket.providers.fundamentals import fundamentals_row
from rocket.providers.ism import ISMIndustryRanking, ISMReport
from rocket.providers.massive import MassiveFundamentals
from rocket.providers.protocols import ProviderResult
from rocket.providers.registry import Registry
from rocket.providers.shorts import acquire_short_snapshot
from rocket.workflows.ism import IsmWorkflow
from rocket.workflows.shorts import ShortsWorkflow, score_ism_short_candidate

LEGACY_REGISTRY = lambda: Registry({"fundamentals": {"primary": "fmp", "fallbacks": ["massive"]}})

NOW = datetime(2026, 9, 8, 15, tzinfo=UTC)


def partial_row(symbol, **fields):
    return ProviderResult(
        O.PARTIAL,
        (
            {
                "symbol": symbol,
                "available_at": NOW.isoformat(),
                "fundamentals_source": "fmp",
                "company_fundamentals": None,
                "provider_attempts": [
                    {
                        "name": "fmp:income_growth",
                        "ticker": symbol,
                        "provider": "fmp",
                        "endpoint": "/income-statement-growth",
                        "retrieved_at": NOW.isoformat(),
                        "status": "UNAVAILABLE",
                        "failure_kind": "EmptyData",
                        "coverage": "0",
                    }
                ],
                **fields,
            },
        ),
        NOW,
        source="fmp",
    )


def mixed_rows(failure_kind="Entitlement"):
    fmp = Mock()
    massive = Mock()

    def primary(symbol):
        if symbol == "F":
            return partial_row(symbol, company_fundamentals=False, eps_growth=0.2, pe_ttm=20)
        if symbol == "CAT":
            return partial_row(symbol, pe_ttm=12, valuation_support=True)
        return partial_row(symbol)

    def fallback(symbol):
        if symbol == "NUE":
            return ProviderResult(
                O.UNAVAILABLE,
                failure_kind=failure_kind,
                source="massive",
                extras={
                    "provider_attempts": [
                        {
                            "name": "massive:income_statements",
                            "ticker": symbol,
                            "provider": "massive",
                            "endpoint": "income-statements",
                            "retrieved_at": NOW.isoformat(),
                            "status": "UNAVAILABLE",
                            "coverage": "0",
                            "failure_kind": failure_kind,
                        }
                    ]
                },
            )
        return ProviderResult(
            O.HEALTHY,
            (
                {
                    "company_fundamentals": True,
                    "eps_growth": -0.2,
                    "eps_kind": "REPORTED",
                    "eps_growth_basis": "reported annual EPS",
                    "available_at": NOW.isoformat(),
                    "pe_ttm": None,
                    "valuation_support": None,
                },
            ),
            NOW,
            source="massive",
        )

    fmp.fundamentals.side_effect = primary
    massive.fetch.side_effect = fallback
    rows = {s: fundamentals_row(s, fmp=fmp, massive=massive, registry=LEGACY_REGISTRY()) for s in ("F", "CAT", "NUE", "TXN")}
    assert [call.args[0] for call in massive.fetch.call_args_list] == [
        "CAT",
        "NUE",
        *(["NUE"] if failure_kind == "ExternalOutage" else []),
        "TXN",
    ]
    return rows


def test_field_recovery_preserves_false_veto_and_exhausted_attempts():
    rows = mixed_rows()
    assert rows["F"]["company_fundamentals"] is False
    assert rows["CAT"]["company_fundamentals"] is True
    assert rows["CAT"]["valuation_support"] is True
    assert rows["CAT"]["field_provenance"]["eps_growth"] == "massive"
    assert rows["CAT"]["field_provenance"]["pe_ttm"] == "fmp"
    assert rows["TXN"]["pe_ttm"] is None
    assert rows["NUE"]["company_fundamentals"] is None
    assert any(
        a["endpoint"] == "/income-statement-growth" for a in rows["NUE"]["provider_attempts"]
    )
    assert any(a["failure_kind"] == "Entitlement" for a in rows["NUE"]["provider_attempts"])
    assert "SECRET" not in json.dumps(rows)


@pytest.mark.parametrize("failure_kind", ["Entitlement", "InvalidProviderData", "ExternalOutage"])
def test_mixed_ism_ranking_and_shorts(monkeypatch, failure_kind):
    rows = mixed_rows(failure_kind)

    def contexts(symbols):
        return {
            s: {
                "fundamentals": rows[s],
                "technical_condition": "healthy",
                "market_state": {
                    "current_price": 101,
                    "as_of": NOW.isoformat(),
                    "available_at": NOW.isoformat(),
                    "source": "fixture",
                },
                "technical_basis": {"average_20": 100, "low_20": 100, "latest_close": 101, "latest_close_at": "2026-09-04T20:00:00+00:00"},
            }
            for s in symbols
        }

    report = ISMReport(
        "manufacturing",
        "August 2026",
        54.6,
        expanding=[ISMIndustryRanking("machinery", "expanding", 1)],
    )
    exposures = {
        "machinery": [
            {"ticker": s, "source": "https://issuer.test", "exposure": "reviewed"} for s in rows
        ]
    }
    ism = IsmWorkflow(exposures=exposures, context_fetcher=contexts).run(
        reports={"manufacturing": report}, now=NOW, research_companies=True
    )
    assert ism.operational.status is O.PARTIAL
    candidates = ism.payload["candidates"]
    assert {r["ticker"]: r["classification"] for r in candidates} == {
        "F": "BUY_CANDIDATE",
        "CAT": "NOT_INTERESTING",
        "NUE": "NEEDS_REVIEW",
        "TXN": "NEEDS_REVIEW",
    }
    assert ism.to_dict()["payload"]["execution_enabled"] is False
    assert next(r for r in candidates if r["ticker"] == "NUE")["context"]["fundamentals"][
        "provider_attempts"
    ]
    monkeypatch.setattr(
        "rocket.providers.shorts._closes", lambda s, c: ([100.0] * 21 + [90.0], NOW.isoformat())
    )
    with httpx.Client() as client:
        snapshots = acquire_short_snapshot(
            universe={s: None for s in rows}, http=client, now=NOW, fundamentals=lambda s: rows[s]
        )
    for row in snapshots:
        row["candidate_sources"] = [{"direction": "short"}]
    shorts = ShortsWorkflow().scan(
        snapshots, now=NOW, scorer=score_ism_short_candidate, strategy="ism_simple"
    )
    assert shorts.operational.status is O.PARTIAL
    scored = {
        r["asset"]: r
        for r in shorts.payload["final_candidates"] + shorts.payload["rejected_candidates"]
    }
    assert scored["F"]["rejection_reason"] == "fundamentals_not_bearish"
    assert scored["CAT"]["rejection_reason"] == "valuation_support"
    assert scored["NUE"]["factor_states"]["company_fundamentals"] == "UNKNOWN"
    assert scored["TXN"]["selected"] is True
    assert shorts.to_dict()["payload"]["execution_enabled"] is False
    assert any(p.to_dict().get("ticker") == "NUE" for p in shorts.operational.providers)


@pytest.mark.parametrize(
    "response,kind",
    [
        ([], "EmptyData"),
        ({"Error Message": "Upgrade plan SECRET"}, "Entitlement"),
        ({"Error": "Invalid API key SECRET"}, "Authentication"),
        ({"unexpected": "SECRET"}, "InvalidProviderData"),
    ],
)
def test_fmp_endpoint_failure_classification(response, kind):
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response))
    ) as client:
        result = FMPClient(api_key="SECRET", http=client).fundamentals("CAT")
    attempts = result.records[0]["provider_attempts"]
    assert all(a["failure_kind"] == kind for a in attempts)
    assert all(a["ticker"] == "CAT" and a["endpoint"] and a["retrieved_at"] for a in attempts)
    assert "SECRET" not in str(result)


@pytest.mark.parametrize(
    "response,kind",
    [
        ({"status": "OK", "results": []}, "EmptyData"),
        ({"status": "NOT_AUTHORIZED", "message": "SECRET"}, "Entitlement"),
        ({"status": "OK", "results": [{}]}, "InsufficientCoverage"),
        ({"status": "OK", "results": ["bad"]}, "InvalidProviderData"),
    ],
)
def test_massive_endpoint_failure_classification(response, kind):
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response))
    ) as client:
        result = MassiveFundamentals(api_key="SECRET", http=client).fetch("CAT", now=NOW)
    assert result.failure_kind == kind
    assert result.extras["provider_attempts"][0]["ticker"] == "CAT"
    assert "SECRET" not in str(result)


def test_real_adapters_recover_empty_eps_and_keep_fmp_valuation():
    from pathlib import Path

    data = json.loads(
        (Path(__file__).parents[1] / "fixtures/fundamentals/massive_cat.json").read_text()
    )

    def handler(req):
        if req.url.host == "api.massive.com":
            assert req.url.params["tickers"] == "CAT"
            assert req.url.params["timeframe"] == "annual"
            return httpx.Response(200, json=data)
        return httpx.Response(
            200, json=[{"symbol": "CAT", "pe": 12}] if req.url.path.endswith("/profile") else []
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        adapter = MassiveFundamentals(api_key="SECRET", http=client)
        massive = Mock()
        massive.fetch.side_effect = lambda symbol: adapter.fetch(symbol, now=NOW)
        row = fundamentals_row(
            "CAT",
            registry=LEGACY_REGISTRY(),
            fmp=FMPClient(api_key="SECRET", http=client),
            massive=massive,
        )
    assert row["eps_growth"] == -0.5
    assert row["pe_ttm"] == 12
    assert row["valuation_support"] is True
    assert row["field_provenance"]["eps_growth"] == "massive"
    assert any(
        a["provider"] == "massive" and a["failure_kind"] is None for a in row["provider_attempts"]
    )
    assert "SECRET" not in str(row)


@pytest.mark.parametrize(
    "code,kind", [(403, "Entitlement"), (503, "ExternalOutage"), (429, "RateLimit")]
)
def test_hard_and_transient_failures_preserve_both_endpoint_traces(code, kind):
    def handler(req):
        return httpx.Response(code, json={"Error": "SECRET"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        row = fundamentals_row(
            "NUE",
            registry=LEGACY_REGISTRY(),
            fmp=FMPClient(api_key="SECRET", http=client),
            massive=MassiveFundamentals(api_key="SECRET", http=client),
        )
    assert row["company_fundamentals"] is None
    assert {a["provider"] for a in row["provider_attempts"]} == {"fmp", "massive"}
    assert all(a["failure_kind"] == ("HardError" if kind == "ExternalOutage" else kind)
               for a in row["provider_attempts"])
    assert "SECRET" not in str(row)


def _provider(growth, *, accounting, window, basis, source, extra=None):
    record = {
        "company_fundamentals": growth < 0,
        "eps_growth": growth,
        "eps_growth_basis": basis,
        "eps_accounting": accounting,
        "eps_window": window,
        "eps_kind": "REPORTED",
        **(extra or {}),
    }
    return ProviderResult(O.HEALTHY, (record,), NOW, source=source)


def test_pep_shaped_opposite_sign_prefers_gaap_ttm_and_flags():
    fmp, edgar, massive = Mock(), Mock(), Mock()
    fmp.fundamentals.return_value = _provider(
        -0.136, accounting="UNSPECIFIED", window="ANNUAL",
        basis="reported annual EPS growth", source="fmp", extra={"pe_ttm": 22},
    )
    edgar.fetch.return_value = _provider(
        0.39, accounting="GAAP", window="TTM",
        basis="reported TTM EPS YoY (FY plus comparable YTD; quarter sum fallback)",
        source="sec.edgar", extra={"eps_ttm": 6.95},
    )
    row = fundamentals_row("PEP", fmp=fmp, edgar=edgar, massive=massive)
    assert row["eps_growth"] == 0.39
    assert row["company_fundamentals"] is False
    assert row["eps_accounting"] == "GAAP"
    assert row["eps_window"] == "TTM"
    assert row["fundamentals_source"] == "sec.edgar"
    assert row["field_provenance"]["eps_growth"] == "sec.edgar"
    assert row["pe_ttm"] == 22
    assert row["field_provenance"]["pe_ttm"] == "fmp"
    assert row["eps_ttm"] == 6.95
    flag = row["eps_provider_disagreement"]
    assert flag["flagged"] is True
    assert flag["reason"] == "opposite_sign"
    assert flag["threshold"] == 0.25
    assert flag["selected_provider"] == "sec.edgar"
    assert [item["provider"] for item in flag["providers"]] == ["fmp", "sec.edgar"]
    assert flag["providers"][0]["eps_growth"] == -0.136
    assert flag["providers"][0]["eps_window"] == "ANNUAL"
    assert flag["providers"][1]["eps_accounting"] == "GAAP"
    massive.fetch.assert_not_called()


def test_same_sign_large_gap_keeps_preferred_basis_and_flags():
    fmp, edgar, massive = Mock(), Mock(), Mock()
    fmp.fundamentals.return_value = _provider(
        0.10, accounting="UNSPECIFIED", window="ANNUAL",
        basis="reported annual EPS growth", source="fmp",
    )
    edgar.fetch.return_value = _provider(
        0.40, accounting="GAAP", window="TTM",
        basis="reported TTM EPS YoY (FY plus comparable YTD; quarter sum fallback)",
        source="sec.edgar",
    )
    row = fundamentals_row("F", fmp=fmp, edgar=edgar, massive=massive)
    assert row["eps_growth"] == 0.40
    assert row["eps_accounting"] == "GAAP"
    assert row["eps_window"] == "TTM"
    assert row["eps_provider_disagreement"]["flagged"] is True
    assert row["eps_provider_disagreement"]["reason"] == "large_gap"
    massive.fetch.assert_not_called()


def test_same_sign_small_gap_records_both_without_flag():
    fmp, edgar, massive = Mock(), Mock(), Mock()
    fmp.fundamentals.return_value = _provider(
        0.10, accounting="UNSPECIFIED", window="ANNUAL",
        basis="reported annual EPS growth", source="fmp",
    )
    edgar.fetch.return_value = _provider(
        0.18, accounting="GAAP", window="QUARTER",
        basis="reported latest fiscal quarter EPS YoY", source="sec.edgar",
    )
    row = fundamentals_row("CAT", fmp=fmp, edgar=edgar, massive=massive)
    assert row["eps_window"] == "QUARTER"
    assert row["fundamentals_source"] == "sec.edgar"
    assert row["eps_provider_disagreement"]["flagged"] is False
    assert row["eps_provider_disagreement"]["reason"] is None
    assert len(row["eps_provider_disagreement"]["providers"]) == 2
    massive.fetch.assert_not_called()


def test_basis_text_is_inferred_when_structured_fields_are_absent():
    fmp, edgar, massive = Mock(), Mock(), Mock()
    fmp.fundamentals.return_value = ProviderResult(
        O.HEALTHY,
        ({"company_fundamentals": True, "eps_growth": -0.2,
          "eps_growth_basis": "reported annual EPS growth"},),
        NOW, source="fmp",
    )
    edgar.fetch.return_value = ProviderResult(O.UNAVAILABLE, failure_kind="Empty", source="sec.edgar")
    row = fundamentals_row("DOW", fmp=fmp, edgar=edgar, massive=massive)
    assert row["eps_accounting"] == "UNSPECIFIED"
    assert row["eps_window"] == "ANNUAL"
    assert row["eps_provider_disagreement"] is None
    massive.fetch.assert_not_called()
