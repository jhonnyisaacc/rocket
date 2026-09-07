from datetime import UTC, datetime

from rocket.models import OperationalStatus, ResearchStatus
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
