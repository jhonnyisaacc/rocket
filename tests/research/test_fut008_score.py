import io
import json
import tarfile

from research.futures.fut008_score import book_samples, start_ms


def test_decision_uses_pre_boundary_book_and_fill_uses_delayed_book(tmp_path):
    day = "2023-04-01"
    start = start_ms(day)
    name = f"BTC-USDT-SWAP-L2orderbook-400lv-{day}"
    path = tmp_path / f"{name}.tar.gz"
    rows = [{"instId": "BTC-USDT-SWAP", "action": "snapshot",
             "ts": str(start + 1), "bids": [["100", "2", "1"]],
             "asks": [["101", "2", "1"]]}]
    for i in range(1, 287):
        boundary = start + i * 300_000
        rows.extend([
            {"instId": "BTC-USDT-SWAP", "action": "update",
             "ts": str(boundary - 1),
             "bids": [["90", "0", "0"], ["100", "2", "1"]], "asks": []},
            {"instId": "BTC-USDT-SWAP", "action": "update",
             "ts": str(boundary),
             "bids": [["100", "0", "0"], ["90", "2", "1"]], "asks": []},
            {"instId": "BTC-USDT-SWAP", "action": "update",
             "ts": str(boundary + 10_000), "bids": [], "asks": []},
        ])
    rows.append({"instId": "BTC-USDT-SWAP", "action": "update",
                 "ts": str(start + 287 * 300_000 + 10_000),
                 "bids": [], "asks": []})
    payload = "".join(json.dumps(row) + "\n" for row in rows).encode()
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo(name + ".data")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    samples = book_samples(path, day)
    assert len(samples) == 286
    assert all(sample["decision"]["bid"] == 100 for sample in samples)
    assert all(sample["entry"]["bid"] == 90 for sample in samples)
    assert all(sample["exit"]["bid"] == 90 for sample in samples)
    assert all(sample["decision"]["age_ms"] == 1 for sample in samples)
    assert all(sample["entry"]["age_ms"] == 0 for sample in samples)
