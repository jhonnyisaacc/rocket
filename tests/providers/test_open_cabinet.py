from copy import deepcopy
from datetime import UTC, datetime

import httpx
import pytest

from rocket.models import OperationalStatus
from rocket.providers.open_cabinet import OpenCabinetProvider, structured_coverage
from rocket.store import ResearchStore
from rocket.workflows.disclosures import DisclosureWorkflow, SourceFamily, normalize_record

NOW = datetime(2026, 9, 8, 12, tzinfo=UTC)
URL = 'https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/abc/$FILE/Trump.pdf'
ROW = {'recordId': 'row1', 'description': 'ABBOTT LABS', 'resolvedTicker': 'ABT',
       'instrumentType': 'common_stock', 'resolutionTier': 'T1', 'verificationState': 'checked',
       'type': 'Purchase', 'date': '2026-06-24', 'sourceUrl': URL, 'amount': '$100,001-$250,000'}


def dataset(rows=None):
    rows = rows if rows is not None else [deepcopy(ROW)]
    return {'exportedAt': '2026-09-07T18:00:00Z', 'officials': [
        {'name': 'Donald Trump Jr.', 'transactions': [ROW], 'transactionCount': 1},
        {'name': 'Trump, Donald J.', 'transactions': rows, 'transactionCount': len(rows)},
    ]}


def acquire(payload, filings=()):
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))) as client:
        return OpenCabinetProvider(http=client).person_history(official_records=filings, now=NOW)


def test_free_export_exact_person_and_official_posting_join():
    filings = [{'subject': 'Donald J. Trump', 'source_url': URL,
                'index_added_at': '2026-08-22T04:21:08'}]
    r = acquire(dataset(), filings)
    assert r.status is OperationalStatus.HEALTHY
    assert len(r.records) == 1
    row = r.records[0]
    assert row['asset'] == 'ABT'
    assert row['eligible_equity_context']
    assert row['disclosure_date'] == '2026-08-22'
    assert row['disclosure_date_basis'] == 'OGE_INDEX_POSTED_DATE'
    assert row['source_family'] == 'secondary'
    assert row['underlying_source_family'] == 'executive'
    assert row['amount_range'] == ROW['amount']


@pytest.mark.parametrize('changes', [
    {'instrumentType': 'corporate_note'}, {'instrumentType': 'etf'},
    {'resolutionTier': 'T2'}, {'resolutionTier': 'T1 name unconfirmed'},
    {'verificationState': 'disputed'}, {'resolvedTicker': None},
])
def test_unresolved_or_non_equity_rows_remain_review(changes):
    r = acquire(dataset([{**ROW, **changes}]))
    assert r.status is OperationalStatus.HEALTHY
    assert not r.records[0]['eligible_equity_context']
    assert r.records[0]['asset'] == ROW['description']


def test_missing_filing_date_is_unknown_not_export_date():
    row = acquire(dataset()).records[0]
    assert row['disclosure_date'] is None
    assert row['disclosure_date_basis'] == 'UNKNOWN'


@pytest.mark.parametrize('mutation', [
    lambda p: p.update(exportedAt='2026-08-01T00:00:00Z'),
    lambda p: p.update(exportedAt='2026-09-09T00:00:00Z'),
    lambda p: p.update(officials=[]),
    lambda p: p['officials'][1].update(transactionCount=2),
    lambda p: p['officials'][1]['transactions'][0].update(sourceUrl='https://fake.test/trump.pdf'),
    lambda p: p['officials'][1]['transactions'][0].update(date='2027-01-01'),
])
def test_bad_exports_fail_closed(mutation):
    payload = dataset()
    mutation(payload)
    r = acquire(payload)
    assert r.status is OperationalStatus.UNAVAILABLE
    assert not r.records


def test_distinct_same_day_rows_survive_and_corrections_replace_identity():
    r = acquire(dataset([ROW, {**ROW, 'recordId': 'row2'}]))
    first, second = [normalize_record(row, family=SourceFamily.SECONDARY) for row in r.records]
    assert first['unique_id'] != second['unique_id']
    revised = normalize_record({**r.records[0], 'asset': 'UNKNOWN', 'eligible_equity_context': False},
                               family=SourceFamily.SECONDARY)
    assert revised['unique_id'] == first['unique_id']
    assert first['amount_range'] == ROW['amount']


def test_secondary_provider_coverage_and_repeat_silence(tmp_path):
    rows = acquire(dataset()).records
    workflow = DisclosureWorkflow(store=ResearchStore(tmp_path))
    args = {'secondary_records': rows, 'now': NOW, 'subjects': ['Donald Trump'],
            'provider_status': {'trump_transaction_history': {
                'status': 'OK', 'source_family': 'secondary', 'record_provider': 'open_cabinet'}}}
    result = workflow.run(**args)
    assert result.operational.providers[0].coverage == 'NEW_RECORDS'
    assert result.payload['new_total'] == 1
    assert workflow.run(**args).to_dict()['presentation']['silent']


FILING = "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/abc/$FILE/Donald-J-Trump-09.8.2026-278T.pdf"
LAG_NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)


def test_newer_278t_is_oc_stale_and_does_not_invent_a_ticker():
    filing = {"subject": "Donald J. Trump", "source_url": FILING, "index_added_at": "2026-09-22T04:21:08",
              "asset": "PUBLIC_FINANCIAL_DISCLOSURE", "transaction_type": "FILING_OBSERVED"}
    coverage = structured_coverage([filing], exported_at="2026-09-14T19:01:49.293Z", now=LAG_NOW, export_usable=True)
    assert coverage["needs_structured_source"] is True
    assert coverage["status"] == "OC_STALE"
    assert coverage["export_lag_days"] == 8
    assert coverage["uncovered_filings"] == [{
        "source_url": FILING, "index_added_at": "2026-09-22T04:21:08",
        "status": "OC_STALE", "needs_structured_source": True,
    }]
    assert "ticker" not in coverage
    assert filing["asset"] == "PUBLIC_FINANCIAL_DISCLOSURE"


def test_joined_278t_is_covered_and_a_current_gap_is_missing_rows():
    filing = {"source_url": FILING, "index_added_at": "2026-09-08T00:00:00"}
    covered = structured_coverage([filing], exported_at="2026-09-14T19:01:49.293Z", covered_urls=[FILING],
                                  now=LAG_NOW, export_usable=True)
    assert covered["needs_structured_source"] is False
    assert covered["status"] == "COVERED"
    missing = structured_coverage([filing], exported_at="2026-09-14T19:01:49.293Z", now=LAG_NOW, export_usable=True)
    assert missing["status"] == "MISSING_STRUCTURED_ROWS"
    assert missing["needs_structured_source"] is True
    annual = {"source_url": FILING.replace("278T.pdf", "278.pdf"), "index_added_at": "2026-09-22T00:00:00"}
    assert structured_coverage([annual], exported_at="2026-09-14T19:01:49.293Z", now=LAG_NOW,
                               export_usable=True)["needs_structured_source"] is False


def test_stale_export_is_oc_stale_without_rows():
    payload = dataset()
    payload["exportedAt"] = "2026-08-01T00:00:00Z"
    result = acquire(payload)
    assert result.status is OperationalStatus.UNAVAILABLE
    assert result.failure_kind == "OC_STALE"
    assert not result.records
    assert result.extras["exported_at"].startswith("2026-08-01")


def test_missing_posting_date_prevents_candidate_promotion(tmp_path):
    from tests.workflows.test_candidate_outputs import context
    rows = acquire(dataset()).records
    result = DisclosureWorkflow(store=ResearchStore(tmp_path)).run(
        historical_records=rows, research_opportunities=True, now=NOW,
        context_fetcher=lambda ts: {t: context() for t in ts})
    assert result.payload['opportunities'][0]['classification'] == 'NEEDS_REVIEW'
    assert result.payload['opportunities'][0]['direction'] == 'unknown'
