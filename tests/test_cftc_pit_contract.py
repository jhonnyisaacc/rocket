"""COT position dates must never become inferred publication timestamps."""

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import httpx

from rocket.models import OperationalStatus
from rocket.providers import cftc, openbb_cftc
from rocket.providers.protocols import ProviderResult

AS_OF = datetime(2026, 9, 22, tzinfo=UTC)
RECEIPT = datetime(2026, 9, 25, 19, 31, tzinfo=UTC)
REPORT = """<pre>
BITCOIN - CHICAGO MERCANTILE EXCHANGE Code-133741
FUTURES ONLY POSITIONS AS OF September 22, 2026
All : 40,000 5,000 15,000 2,000 8,000 7,000
ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE Code-146021
FUTURES ONLY POSITIONS AS OF September 22, 2026
All : 20,000 2,000 8,000 1,000 4,000 3,000
</pre>"""


def test_parse_position_date_has_unknown_publication_and_vintage():
    rows = cftc.parse_cftc_report(REPORT)
    for row in rows.values():
        assert row["as_of_date"] == "2026-09-22"
        assert row["event_time"] == AS_OF.isoformat()
        assert row["event_time_precision"] == "date"
        assert row["release_date"] is None
        assert row["available_at"] is None
        assert row["historical_available_at"] is None
        assert row["vintage_id"] is None
        assert row["historical_pit"] is False


def _fetch(monkeypatch):
    sequence = []

    def response(request):
        sequence.append("response")
        return httpx.Response(200, text=REPORT)

    def now(zone):
        sequence.append("receipt")
        assert zone is UTC
        return RECEIPT

    clock = Mock(wraps=datetime)
    clock.now.side_effect = now
    monkeypatch.setattr(cftc, "datetime", clock)
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        result = cftc.fetch_cftc_direct(http=client)
    assert sequence == ["response", "receipt"]
    return result


def test_live_receipt_follows_response_and_preserves_byte_identity(monkeypatch):
    result = _fetch(monkeypatch)
    expected_hash = hashlib.sha256(REPORT.encode()).hexdigest()
    assert result.retrieved_at == RECEIPT
    assert result.extras["source_sha256"] == expected_hash
    for row in result.records:
        assert row["available_at"] == RECEIPT.isoformat()
        assert row["ingested_at"] == RECEIPT.isoformat()
        assert row["source_sha256"] == expected_hash
        assert row["release_date"] is None
        assert row["historical_available_at"] is None
        assert row["historical_pit"] is False


def test_position_date_cannot_make_later_observed_report_eligible(monkeypatch):
    result = _fetch(monkeypatch)
    context = cftc.cot_context_from_result(result, now=AS_OF + timedelta(hours=12))
    assert context["knowledge_time_status"] == "LATE"
    assert context["status"] == "LATE"
    assert context["regime"] == "unknown"
    assert all(row["point_in_time"]["available_at"] == RECEIPT.isoformat()
               for row in context["markets"].values())


def test_after_receipt_live_context_eligible_without_claiming_historical_pit(monkeypatch):
    result = _fetch(monkeypatch)
    context = cftc.cot_context_from_result(result, now=RECEIPT + timedelta(seconds=1))
    assert context["knowledge_time_status"] == "ELIGIBLE"
    assert context["status"] == "OK"
    assert context["regime"] == "bullish"
    assert context["historical_pit"] is False
    assert context["historical_available_at"] is None


def test_parser_only_operational_freshness_does_not_assert_pit():
    result = ProviderResult(OperationalStatus.HEALTHY,
                            tuple(cftc.parse_cftc_report(REPORT).values()))
    context = cftc.cot_context_from_result(result, now=RECEIPT)
    assert context["knowledge_time_status"] == "UNKNOWN"
    assert context["historical_pit"] is False
    assert all(row["point_in_time"]["available_at"] is None
               for row in context["markets"].values())


def test_provider_result_receipt_is_conservative_fallback_for_legacy_records():
    rows = tuple({"asset": asset, "as_of_date": AS_OF.date().isoformat(),
                  "bias": "bullish"} for asset in ("BTC", "ETH"))
    result = ProviderResult(OperationalStatus.HEALTHY, rows, RECEIPT, source="OpenBB/CFTC")
    context = cftc.cot_context_from_result(result, now=RECEIPT - timedelta(seconds=1))
    assert context["knowledge_time_status"] == "LATE"
    assert context["regime"] == "unknown"
    assert all(row["historical_pit"] is False for row in context["markets"].values())


def test_openbb_evaluation_clock_cannot_become_its_source_receipt(monkeypatch):
    clock = Mock(wraps=datetime)
    clock.now.return_value = RECEIPT
    monkeypatch.setattr(openbb_cftc, "datetime", clock)

    def fetcher(**params):
        return [{"date": "2026-09-22", "cftc_contract_market_code":
                 params["code"].removeprefix("CFTC_"),
                 "futonly_or_combined": "FutOnly", "open_interest_all": 100,
                 "non_commercial_positions_long_all": 10,
                 "non_commercial_positions_short_all": 20}]

    decision = AS_OF + timedelta(hours=12)
    result = openbb_cftc.OpenBBCFTC(fetcher=fetcher).fetch(now=decision)
    assert result.status is OperationalStatus.HEALTHY
    assert result.retrieved_at == RECEIPT
    assert all(row["available_at"] == RECEIPT.isoformat() for row in result.records)
    assert cftc.cot_context_from_result(result, now=decision)["knowledge_time_status"] == "LATE"
