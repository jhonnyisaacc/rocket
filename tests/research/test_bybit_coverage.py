"""Coverage distinguishes observed source rows from launch metadata."""

import json

from research.futures.bybit_coverage import collect_window, coverage, source_response
from research.futures.bybit_source_audit import DAY_MS


def test_coverage_reports_internal_missing_days_and_funding_overlap():
    origin = 1_577_836_800_000
    rows = [origin, origin + DAY_MS, origin + 3 * DAY_MS]
    funding = [origin + 8 * 3_600_000, origin + DAY_MS,
               origin + DAY_MS + 8 * 3_600_000]
    result = coverage(rows, funding)
    assert result["price_days"] == 3
    assert result["internal_price_gap_days"] == 1
    assert result["price_days_with_funding_stamp"] == 2
    assert result["first_price_ms"] == origin
    assert result["last_price_ms"] == origin + 3 * DAY_MS


def test_empty_funding_page_may_omit_symbol(tmp_path):
    start = 1_577_836_800_000
    end = start + DAY_MS
    path = tmp_path / "raw" / f"OLDUSDT_funding_{start}_{end}_limit200.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"retCode": 0, "result": {"category": "linear", "list": []}}))
    stamps, record = source_response(tmp_path, "OLDUSDT", "funding", start, end)
    assert stamps == []
    assert record["rows"] == 0


def test_funding_page_checks_symbol_on_rows(tmp_path):
    start = 1_577_836_800_000
    end = start + DAY_MS
    path = tmp_path / "raw" / f"OLDUSDT_funding_{start}_{end}_limit200.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"retCode": 0, "result": {"category": "linear", "list": [
        {"symbol": "OTHERUSDT", "fundingRateTimestamp": str(start + 8 * 3_600_000)}]}}))
    try:
        source_response(tmp_path, "OLDUSDT", "funding", start, end)
    except ValueError as error:
        assert "funding symbol" in str(error)
    else:
        raise AssertionError("mismatched funding symbol accepted")


def test_funding_paginates_backward_at_200_record_cap(monkeypatch, tmp_path):
    start = 1_577_836_800_000
    stamps = [start + i * 8 * 3_600_000 for i in range(260)]
    end = start + 90 * DAY_MS
    calls = []

    def fake_response(_output, _symbol, _kind, first, last):
        page = sorted((stamp for stamp in stamps if first <= stamp < last), reverse=True)[:200]
        calls.append(last)
        return page, {"rows": len(page)}

    monkeypatch.setattr("research.futures.bybit_coverage.source_response", fake_response)
    observed, sources = collect_window(tmp_path, "TESTUSDT", "funding", start, end)
    assert set(observed) == set(stamps)
    assert [item["rows"] for item in sources] == [200, 60]
    assert calls[1] == min(stamps[-200:])
