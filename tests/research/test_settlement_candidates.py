"""Settlement candidates use the historically correct averaging window."""

import io
import zipfile
from pathlib import Path

from research.futures.settlement_candidates import build, index_envelope, index_mean


def test_minute_index_average_uses_only_minutes_before_cutoff(tmp_path: Path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("index.csv", "open_time,open,high,low,close\n"
                         "60000,1,1.2,0.8,1\n120000,2,2.2,1.8,2\n"
                         "180000,100,100,100,100\n")
    path = tmp_path / "index.zip"
    path.write_bytes(output.getvalue())
    assert index_mean(path, 180000, 2) == 1.5
    assert index_envelope(path, 180000, 2) == {
        "mean_low": 1.3, "mean_close": 1.5, "mean_high": 1.7000000000000002,
    }


def test_notice_cutoff_override_is_used(tmp_path: Path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("index.csv", "open_time,open,high,low,close\n"
                         + "".join(f"{minute * 60000},1,1,1,1\n"
                                   for minute in range(330, 391)))
    key = "index.zip"
    (tmp_path / key).write_bytes(output.getvalue())
    probes = {"results": [{
        "symbol": "PORT3USDT", "last_active_minute_ms": 390 * 60000,
        "indexPriceKlines_key": key, "indexPriceKlines_sha256": "index-hash",
        "klines_key": "trade.zip", "klines_sha256": "trade-hash",
    }]}
    notices = {"events": [{"date": "1970-01-01", "settlement_time_utc": "06:30",
                           "source_url": "https://example.com/notice",
                           "symbol_sources": {"PORT3USDT": "https://example.com/port3"}}]}
    candidates = build(probes, notices, tmp_path)
    assert len(candidates) == 1
    assert candidates[0]["assumed_settlement_ms"] == 390 * 60000
    assert candidates[0]["latest_candidate_settlement_ms"] == 391 * 60000
    assert candidates[0]["approx_index_settlement_price"] == 1
    assert candidates[0]["cutoff_sensitivity_mean_low"] == 1
    assert candidates[0]["notice_candidate_url"] == "https://example.com/port3"
