from datetime import UTC, datetime

import pytest

from rocket.models import OperationalStatus, ResearchStatus
from rocket.providers.open_cabinet import structured_coverage
from rocket.store import ResearchStore
from rocket.workflows.disclosures import DisclosureWorkflow
from tests.harness import assert_research_result, is_registered

NOW = datetime(2026, 9, 7, 15, tzinfo=UTC)


def test_disclosures_registered():
    assert is_registered("disclosures")


def test_healthy_no_new_records_is_no_setup(tmp_path):
    store = ResearchStore(tmp_path)
    workflow = DisclosureWorkflow(store=store)
    first = workflow.run(
        congress_records=[{"subject": "A", "asset": "FILING", "transaction_type": "FILING", "source_url": "https://house.test/a.pdf"}],
        now=NOW,
        provider_status={"congress": {"status": "OK"}, "executive": {"status": "OK"}},
    )
    assert_research_result(first)
    second = workflow.run(
        congress_records=[{"subject": "A", "asset": "FILING", "transaction_type": "FILING", "source_url": "https://house.test/a.pdf"}],
        now=NOW,
        provider_status={"congress": {"status": "OK"}, "executive": {"status": "OK"}},
    )
    assert_research_result(second)
    assert second.status is ResearchStatus.NO_SETUP
    assert second.operational.status is OperationalStatus.HEALTHY
    assert second.payload["research_result"] == "NO_NEW_RECORDS"


def test_all_providers_failed_is_not_no_setup(tmp_path):
    result = DisclosureWorkflow(store=ResearchStore(tmp_path)).run(
        now=NOW,
        provider_status={"congress": {"status": "UNAVAILABLE"}, "executive": {"status": "UNAVAILABLE"}},
    )
    assert_research_result(result)
    assert result.operational.status is OperationalStatus.UNAVAILABLE
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert result.payload["research_result"] == "PROVIDER_FAILURE"
    assert result.payload["disclosure_is_not_a_buy_signal"] is True


def test_secondary_fmp_rows_are_not_official_filings(tmp_path):
    result = DisclosureWorkflow(store=ResearchStore(tmp_path)).run(
        secondary_records=[
            {
                "subject": "Jane Doe",
                "asset": "AAPL",
                "transaction_type": "Purchase",
                "transaction_date": "2026-08-01",
                "source_url": "https://efdsearch.senate.gov/x",
                "provider": "fmp",
            }
        ],
        now=NOW,
        provider_status={"congress": {"status": "OK"}, "executive": {"status": "OK"}, "secondary": {"status": "OK"}},
    )
    assert_research_result(result)
    assert result.payload["records"][0]["source_family"] == "secondary"
    assert result.payload["records"][0]["record_semantics"] == "SECONDARY_TRANSACTION_ROW"
    assert result.payload["disclosure_is_not_a_buy_signal"] is True


TRUMP_278T = "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/abc/$FILE/Donald-J-Trump-09.8.2026-278T.pdf"


def _trump_filing():
    return {
        "subject": "Donald J. Trump",
        "asset": "PUBLIC_FINANCIAL_DISCLOSURE",
        "transaction_type": "FILING_OBSERVED",
        "source_url": TRUMP_278T,
        "provider": "official_oge",
        "index_added_at": "2026-09-22T04:21:08",
    }


def test_seen_278t_without_open_cabinet_rows_is_not_silent(tmp_path):
    filing = _trump_filing()
    coverage = structured_coverage(
        [filing], exported_at="2026-09-14T19:01:49.293Z", now=datetime(2026, 9, 23, tzinfo=UTC), export_usable=True,
    )
    workflow = DisclosureWorkflow(store=ResearchStore(tmp_path))
    args = {
        "executive_records": [filing],
        "now": NOW,
        "provider_status": {"executive": {"status": "OK"}, "congress": {"status": "OK"}},
        "structured_coverage": coverage,
    }
    first = workflow.run(**args)
    assert_research_result(first)
    assert first.payload["records"][0]["asset"] == "PUBLIC_FINANCIAL_DISCLOSURE"
    assert first.payload["records"][0]["transaction_type"] == "FILING_OBSERVED"
    assert first.payload["records"][0]["record_semantics"] == "FILING_NOT_TRADE_ROW"
    assert first.payload["records"][0]["needs_structured_source"] is True
    assert first.payload["structured_coverage"]["status"] == "OC_STALE"
    second = workflow.run(**args)
    assert_research_result(second)
    assert second.payload["new_total"] == 0
    assert second.status is ResearchStatus.ACTION_REQUIRED
    assert second.payload["research_result"] == "NO_NEW_RECORDS"
    assert second.to_dict()["presentation"]["silent"] is False
    assert any("Quiver" in warning for warning in second.warnings)


def test_executive_outage_is_not_quiet_and_recovery_rescans(tmp_path):
    store = ResearchStore(tmp_path)
    workflow = DisclosureWorkflow(store=store)
    outage = workflow.run(
        now=NOW,
        provider_status={
            "congress": {"status": "OK"},
            "executive": {"status": "UNAVAILABLE", "failure_kind": "ExternalOutage"},
        },
    )
    assert_research_result(outage)
    assert outage.status is ResearchStatus.ACTION_REQUIRED
    assert outage.operational.status is OperationalStatus.PARTIAL
    assert outage.payload["research_result"] == "PROVIDER_FAILURE"
    assert outage.to_dict()["presentation"]["silent"] is False
    assert store.load_state("disclosures_seen")["unique_ids"] == []
    assert "scanned" not in store.load_state("disclosures_executive")
    recovered = workflow.run(
        executive_records=[_trump_filing()],
        now=NOW,
        provider_status={"congress": {"status": "OK"}, "executive": {"status": "OK"}},
    )
    assert_research_result(recovered)
    assert recovered.payload["executive_recovery_rescan"] is True
    assert recovered.payload["new_total"] == 1
    assert recovered.payload["research_result"] == "NEW_RECORDS"


@pytest.mark.parametrize("kind", ["Entitlement", "RateLimit"])
def test_optional_pelosi_secondary_does_not_force_action(tmp_path, kind):
    result = DisclosureWorkflow(store=ResearchStore(tmp_path)).run(
        now=NOW,
        provider_status={
            "congress:2026": {"status": "OK"},
            "pelosi_secondary_history": {
                "status": "UNAVAILABLE", "failure_kind": kind, "optional": True,
                "source_family": "secondary", "record_provider": "fmp",
            },
        },
    )
    assert_research_result(result)
    assert result.status is ResearchStatus.NO_SETUP
    assert result.operational.status is OperationalStatus.HEALTHY
    assert result.payload["research_result"] == "NO_NEW_RECORDS"
    by_name = {provider.name: provider for provider in result.operational.providers}
    assert by_name["congress:2026"].status is OperationalStatus.HEALTHY
    assert by_name["pelosi_secondary_history"].status is OperationalStatus.UNAVAILABLE
    assert by_name["pelosi_secondary_history"].failure_kind == kind


def _senate_status(status):
    return {
        "congress:2026": {"status": "OK", "source_family": "congress", "record_provider": "official_house_disclosures"},
        "executive": {"status": "OK"},
        "senate_efd": {
            "status": status,
            "failure_kind": status,
            "edge_reference": "18.4818d017.1791288668.5d09d74a",
            "source_family": "congress",
            "record_provider": "official_senate_efd",
        },
    }


@pytest.mark.parametrize("status", ["BLOCKED", "RateLimit"])
def test_senate_degraded_keeps_house_and_oge_visible(tmp_path, status):
    filing = {
        "subject": "Nancy Pelosi",
        "asset": "FINANCIAL_DISCLOSURE_FILING",
        "transaction_type": "FILING",
        "source_url": "https://house.test/a.pdf",
        "provider": "official_house_disclosures",
    }
    store = ResearchStore(tmp_path)
    workflow = DisclosureWorkflow(store=store)
    first = workflow.run(
        congress_records=[filing],
        now=NOW,
        provider_status=_senate_status(status),
        subjects=["Nancy Pelosi"],
    )
    assert_research_result(first)
    assert first.operational.status is OperationalStatus.PARTIAL
    assert first.payload["research_result"] == "NEW_RECORDS"
    assert first.payload["records"][0]["subject_filer"] == "Nancy Pelosi"
    assert first.payload["provider_status"]["senate_efd"]["status"] == status
    assert "research_result" not in first.payload["provider_status"]["senate_efd"]
    assert first.payload["provider_status"]["congress:2026"]["status"] == "OK"
    assert first.payload["provider_status"]["executive"]["status"] == "OK"
    assert first.to_dict()["presentation"]["silent"] is False
    by_name = {provider.name: provider for provider in first.operational.providers}
    assert by_name["congress:2026"].status is OperationalStatus.HEALTHY
    assert by_name["executive"].status is OperationalStatus.HEALTHY
    assert by_name["senate_efd"].status is OperationalStatus.UNAVAILABLE
    assert by_name["senate_efd"].failure_kind == status
    second = workflow.run(
        congress_records=[filing],
        now=NOW,
        provider_status=_senate_status(status),
        subjects=["Nancy Pelosi"],
    )
    assert_research_result(second)
    assert second.payload["new_total"] == 0
    assert second.operational.status is OperationalStatus.PARTIAL
    assert second.payload["research_result"] == "NO_NEW_RECORDS"
    assert second.to_dict()["presentation"]["silent"] is False


def test_senate_rows_survive_person_filter_and_dedupe_by_record_id(tmp_path):
    stock = {
        "subject": "Sheldon Whitehouse",
        "asset": "JPM",
        "transaction_type": "Sale (Partial)",
        "transaction_date": "2026-09-04",
        "disclosure_date": "2026-10-01",
        "source_url": "https://efdsearch.senate.gov/search/view/ptr/11111111-1111-1111-1111-111111111111/",
        "source_record_id": "11111111-1111-1111-1111-111111111111:1",
        "provider": "official_senate_efd",
        "eligible_equity_context": True,
        "record_semantics": "OFFICIAL_TRANSACTION_ROW",
    }
    other = {
        "subject": "Someone Else",
        "asset": "FINANCIAL_DISCLOSURE_FILING",
        "transaction_type": "FILING",
        "source_url": "https://house.test/other.pdf",
        "provider": "official_house_disclosures",
    }
    pelosi = {
        "subject": "Nancy Pelosi",
        "asset": "FINANCIAL_DISCLOSURE_FILING",
        "transaction_type": "FILING",
        "source_url": "https://house.test/pelosi.pdf",
        "provider": "official_house_disclosures",
    }
    store = ResearchStore(tmp_path)
    workflow = DisclosureWorkflow(store=store)
    first = workflow.run(
        congress_records=[stock, other, pelosi],
        now=NOW,
        provider_status={"congress:2026": {"status": "OK"}, "senate_efd": {"status": "HEALTHY"}},
        subjects=["Nancy Pelosi"],
    )
    assert_research_result(first)
    names = {row["subject_filer"] for row in first.payload["records"]}
    assert names == {"Sheldon Whitehouse", "Nancy Pelosi"}
    second = workflow.run(
        congress_records=[stock, pelosi],
        now=NOW,
        provider_status={"congress:2026": {"status": "OK"}, "senate_efd": {"status": "HEALTHY"}},
        subjects=["Nancy Pelosi"],
    )
    assert second.payload["new_total"] == 0


def test_amendment_rows_stay_in_the_inbox_without_a_second_trade(tmp_path):
    original = {
        "subject": "Sheldon Whitehouse",
        "asset": "JPM",
        "transaction_type": "Purchase",
        "transaction_date": "2026-08-01",
        "disclosure_date": "2026-08-20",
        "source_url": "https://efdsearch.senate.gov/search/view/ptr/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/",
        "source_record_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa:1",
        "provider": "official_senate_efd",
        "eligible_equity_context": True,
        "amount_range": "$1,001 - $15,000",
        "record_semantics": "OFFICIAL_TRANSACTION_ROW",
    }
    amendment = {
        **original,
        "source_url": "https://efdsearch.senate.gov/search/view/ptr/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/",
        "source_record_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb:1",
        "amendment": True,
        "amendment_label": "Amendment 1",
    }
    result = DisclosureWorkflow(store=ResearchStore(tmp_path)).run(
        congress_records=[original, amendment],
        now=NOW,
        provider_status={"senate_efd": {"status": "HEALTHY", "source_family": "congress", "record_provider": "official_senate_efd"}},
        research_opportunities=True,
        context_fetcher=lambda tickers: {},
        historical_price_fetcher=lambda ticker: {},
        portfolio_tickers=[],
        watch_tickers=[],
    )
    assert_research_result(result)
    assert result.payload["new_total"] == 2
    tagged = [row for row in result.payload["records"] if row.get("amendment")]
    assert len(tagged) == 1
    assert tagged[0]["amendment_label"] == "Amendment 1"
    assert tagged[0]["source_record_id"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb:1"
    assert result.payload["historical_scope"]["transaction_records"] == 1
    assert len(result.payload["opportunities"]) == 1
