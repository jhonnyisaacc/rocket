from copy import deepcopy
from datetime import UTC, datetime

import httpx
import pytest

from rocket.models import OperationalStatus
from rocket.providers.open_cabinet import (
    OpenCabinetProvider,
    issuer_tickers_from_company_file,
    load_issuer_tickers,
    structured_coverage,
)
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


def acquire(payload, filings=(), issuer_tickers=None):
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))) as client:
        return OpenCabinetProvider(http=client, issuer_tickers=issuer_tickers).person_history(
            official_records=filings, now=NOW)


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


def untyped(record_id, description, **extra):
    return {**ROW, 'recordId': record_id, 'description': description, 'resolvedTicker': None,
            'instrumentType': None, 'resolutionTier': None, 'ticker': None, **extra}


ISSUERS = {'PTC INC.': 'PTC', 'PTC THERAPEUTICS, INC.': 'PTCT', 'MICROSOFT CORP': 'MSFT'}
MUNI = 'ALABAMA FEDL AID HWY FIN AUTH SPL OBLIG REV SER A B/E PTC 5.00 % Due Sep 1, 2035'


def test_untyped_ptc_inc_resolves_and_muni_ptc_does_not():
    rows = [
        untyped('buy', 'PTC INC', type='Purchase', date='2026-07-20', amount='$500,001-$1,000,000'),
        untyped('sell', 'PTC INC', type='Sale', date='2026-07-17', amount='$1,001-$15,000'),
        untyped('ther', 'PTC THERAPEUTICS INC', type='Sale', date='2026-07-29', amount='$15,001-$50,000'),
        untyped('muni', MUNI, type='Purchase', date='2026-07-17', amount='$100,001-$250,000'),
        untyped('marker', 'B/E PTC 5.00 % Due 09/01/2031'),
    ]
    result = acquire(dataset(rows), issuer_tickers=ISSUERS)
    assert result.status is OperationalStatus.HEALTHY
    by_id = {row['source_record_id']: row for row in result.records}
    purchase = by_id['buy']
    assert purchase['resolved_ticker'] == 'PTC'
    assert purchase['asset'] == 'PTC'
    assert purchase['asset_type'] == 'common_stock'
    assert purchase['eligible_equity_context'] is True
    assert purchase['resolution_tier'] == 'sec_exact_name'
    assert purchase['description'] == 'PTC INC'
    assert by_id['sell']['resolved_ticker'] == 'PTC'
    assert by_id['sell']['eligible_equity_context'] is True
    therapeutics = by_id['ther']
    assert therapeutics['resolved_ticker'] == 'PTCT'
    assert therapeutics['asset'] == 'PTCT'
    assert therapeutics['asset_type'] == 'common_stock'
    assert therapeutics['eligible_equity_context'] is True
    for record_id in ('muni', 'marker'):
        bond = by_id[record_id]
        assert bond['resolved_ticker'] is None
        assert bond['eligible_equity_context'] is False
        assert bond['asset_type'] == 'municipal_bond'
        assert bond['asset'] == bond['description']


@pytest.mark.parametrize('description,asset_type', [
    ('VANGUARD TOTAL STOCK MARKET ETF', 'etf'),
    ('NUVEEN MUNICIPAL BOND FUND', 'mutual_fund'),
    ('MICROSOFT B/E 03.300% 020627', 'corporate_note'),
])
def test_untyped_funds_notes_and_etfs_stay_non_equity(description, asset_type):
    row = acquire(dataset([untyped('n', description)]), issuer_tickers=ISSUERS).records[0]
    assert row['asset_type'] == asset_type
    assert row['resolved_ticker'] is None
    assert row['eligible_equity_context'] is False
    assert row['asset'] == description


def test_name_match_is_the_whole_title_and_ambiguous_titles_stay_open():
    embedded = acquire(dataset([untyped('part', 'HOLDINGS PTC INC')]), issuer_tickers=ISSUERS).records[0]
    assert embedded['resolved_ticker'] is None
    assert embedded['asset_type'] is None
    assert embedded['eligible_equity_context'] is False
    ambiguous = acquire(dataset([untyped('amb', 'ACME INC')]), issuer_tickers={
        'ACME INC': 'ACME', 'ACME, INC.': 'ACMX',
    }).records[0]
    assert ambiguous['resolved_ticker'] is None
    assert ambiguous['eligible_equity_context'] is False
    missing = acquire(dataset([untyped('miss', 'NOT A LISTED COMPANY INC')]), issuer_tickers=ISSUERS).records[0]
    assert missing['resolved_ticker'] is None
    assert missing['asset'] == 'NOT A LISTED COMPANY INC'
    assert missing['asset_type'] is None


def test_disputed_untyped_name_is_not_promoted():
    row = acquire(dataset([untyped('d', 'PTC INC', verificationState='disputed')]),
                  issuer_tickers=ISSUERS).records[0]
    assert row['resolved_ticker'] is None
    assert row['eligible_equity_context'] is False
    assert row['asset'] == 'PTC INC'


def test_existing_t1_ticker_is_not_replaced_by_the_name_map():
    row = acquire(dataset(), issuer_tickers={'ABBOTT LABS': 'WRONG'}).records[0]
    assert row['asset'] == 'ABT'
    assert row['resolved_ticker'] == 'ABT'
    assert row['asset_type'] == 'common_stock'
    assert row['resolution_tier'] == 'T1'
    assert row['eligible_equity_context'] is True


def test_company_tickers_exact_title_collapses_punctuation_and_collisions():
    names = issuer_tickers_from_company_file({
        '0': {'ticker': 'ptc', 'title': 'PTC INC.'},
        '1': {'ticker': 'PTCT', 'title': 'PTC THERAPEUTICS, INC.'},
        '2': {'ticker': 'AAA', 'title': 'ACME INC'},
        '3': {'ticker': 'AAB', 'title': 'ACME, INC.'},
        '4': {'ticker': 'not a ticker', 'title': 'SKIP ME INC'},
    })
    assert names['PTC INC'] == 'PTC'
    assert names['PTC THERAPEUTICS INC'] == 'PTCT'
    assert names['ACME INC'] is None
    assert 'SKIP ME INC' not in names


def test_sec_title_outage_leaves_the_export_healthy(monkeypatch):
    class Broken:
        def _get(self, *args, **kwargs):
            raise RuntimeError('sec down')

    monkeypatch.setattr('rocket.providers.edgar.SECEDGAR', Broken)
    result = acquire(dataset([untyped('p', 'PTC INC')]))
    assert result.status is OperationalStatus.HEALTHY
    assert result.failure_kind is None
    row = result.records[0]
    assert row['resolved_ticker'] is None
    assert row['asset'] == 'PTC INC'
    assert row['eligible_equity_context'] is False
    assert load_issuer_tickers(NOW) == {}


def test_missing_posting_date_prevents_candidate_promotion(tmp_path):
    from tests.workflows.test_candidate_outputs import context
    rows = acquire(dataset()).records
    result = DisclosureWorkflow(store=ResearchStore(tmp_path)).run(
        historical_records=rows, research_opportunities=True, now=NOW,
        context_fetcher=lambda ts: {t: context() for t in ts})
    assert result.payload['opportunities'][0]['classification'] == 'NEEDS_REVIEW'
    assert result.payload['opportunities'][0]['direction'] == 'unknown'
