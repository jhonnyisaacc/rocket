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
