"""Settlement candidates use the historically correct averaging window."""

import io
import zipfile
from pathlib import Path

from research.futures.settlement_candidates import build, index_mean


def test_minute_index_average_uses_only_minutes_before_cutoff(tmp_path: Path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("index.csv", "open_time,open,high,low,close\n"
                         "60000,1,1,1,1\n120000,2,2,2,2\n180000,100,100,100,100\n")
    path = tmp_path / "index.zip"
    path.write_bytes(output.getvalue())
    assert index_mean(path, 180000, 2) == 1.5


def test_notice_cutoff_override_is_used(tmp_path: Path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("index.csv", "open_time,open,high,low,close\n"
                         + "".join(f"{minute * 60000},1,1,1,1\n"
                                   for minute in range(330, 390)))
    key = "index.zip"
    (tmp_path / key).write_bytes(output.getvalue())
    probes = {"results": [{
        "symbol": "PORT3USDT", "last_active_minute_ms": 390 * 60000,
        "indexPriceKlines_key": key, "indexPriceKlines_sha256": "index-hash",
        "klines_key": "trade.zip", "klines_sha256": "trade-hash",
    }]}
    notices = {"events": [{"date": "1970-01-01", "settlement_time_utc": "06:30",
                           "source_url": "https://example.com/notice"}]}
    candidates = build(probes, notices, tmp_path)
    assert len(candidates) == 1
    assert candidates[0]["assumed_settlement_ms"] == 390 * 60000
    assert candidates[0]["approx_index_settlement_price"] == 1
