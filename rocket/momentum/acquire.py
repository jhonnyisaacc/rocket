"""Checksum-verified Binance archive acquisition. Read-only network fetch.

Downloads monthly zips + .CHECKSUM files for the fixed calendar window,
verifies sha256, writes a manifest (file, bytes, sha256, vintage). Never
substitutes other windows or live context. Re-runnable: skips verified
files already on disk.
"""

from __future__ import annotations

import json
import os
import urllib.request
import zipfile
from datetime import UTC, datetime

BASE = "https://data.binance.vision/data"
USER_AGENT = "rocket-research"

ARCHIVES = {
    "spot_klines_1h": "spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-{ym}.zip",
    "futures_klines_1h": "futures/um/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-{ym}.zip",
    "funding_rate": "futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-{ym}.zip",
}

FIRST_MONTH = {
    "spot_klines_1h": "2019-01",
    "futures_klines_1h": "2020-01",
    "funding_rate": "2020-01",
}
LAST_MONTH = "2025-12"
METRICS_START = "2021-01-01"  # daily metrics; exact first date discovered at fetch.


def month_range(first: str, last: str) -> list[str]:
    y, m = int(first[:4]), int(first[5:7])
    ly, lm = int(last[:4]), int(last[5:7])
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def fetch_monthly(kind: str, ym: str, directory: str, *, timeout: int = 60) -> dict:
    path = ARCHIVES[kind].format(ym=ym)
    dest = os.path.join(directory, kind, os.path.basename(path))
    checksum_url = f"{BASE}/{path}.CHECKSUM"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    expected = _get(checksum_url, timeout).decode().strip().split()[0]
    if os.path.exists(dest):
        from rocket.momentum.bars import sha256_file

        if sha256_file(dest) == expected:
            return {"file": dest, "sha256": expected, "skipped": True}
    data = _get(f"{BASE}/{path}", timeout)
    with open(dest, "wb") as handle:
        handle.write(data)
    from rocket.momentum.bars import sha256_file, verify_checksum

    with open(dest + ".CHECKSUM", "wb") as handle:
        handle.write(f"{expected}  {os.path.basename(path)}\n".encode())
    verify_checksum(dest, expected)
    return {"file": dest, "sha256": expected, "skipped": False,
            "bytes": len(data)}


def fetch_metrics_day(day: str, directory: str, *, timeout: int = 60) -> dict | None:
    """Daily futures metrics (open interest). Returns None when the day is
    absent upstream (pre-coverage era); absence is recorded, not imputed."""
    name = f"BTCUSDT-metrics-{day}.zip"
    dest = os.path.join(directory, "metrics", name)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        expected = _get(f"{BASE}/futures/um/daily/metrics/BTCUSDT/{name}.CHECKSUM", timeout).decode().strip().split()[0]
    except Exception:
        return None
    from rocket.momentum.bars import sha256_file, verify_checksum

    if not (os.path.exists(dest) and sha256_file(dest) == expected):
        data = _get(f"{BASE}/futures/um/daily/metrics/BTCUSDT/{name}", timeout)
        with open(dest, "wb") as handle:
            handle.write(data)
        verify_checksum(dest, expected)
    return {"file": dest, "sha256": expected}


def acquire_all(directory: str) -> dict:
    """Fetch every archive in the fixed window. Returns the manifest."""
    manifest = {"acquired_at": datetime.now(UTC).isoformat(), "files": {}, "missing": []}
    for kind in ARCHIVES:
        for ym in month_range(FIRST_MONTH[kind], LAST_MONTH):
            try:
                manifest["files"][f"{kind}/{ym}"] = fetch_monthly(kind, ym, directory)
            except Exception as exc:
                manifest["missing"].append({"key": f"{kind}/{ym}", "error": f"{type(exc).__name__}: {exc}"})
    # Daily metrics from METRICS_START to LAST_MONTH end.
    y, m, d = int(METRICS_START[:4]), int(METRICS_START[5:7]), int(METRICS_START[8:10])
    from datetime import date, timedelta

    day = date(y, m, d)
    end = date(2025, 12, 31)
    n_metrics = 0
    while day <= end:
        iso = day.isoformat()
        try:
            got = fetch_metrics_day(iso, directory)
        except Exception as exc:
            manifest["missing"].append({"key": f"metrics/{iso}", "error": f"{type(exc).__name__}: {exc}"})
            got = None
        if got is None:
            manifest["missing"].append({"key": f"metrics/{iso}", "error": "absent upstream"})
        else:
            n_metrics += 1
        day += timedelta(days=1)
    manifest["n_metrics_days"] = n_metrics
    with open(os.path.join(directory, "MANIFEST.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    return manifest


def read_csv_from_zip(path: str) -> str:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"{path}: expected 1 csv, found {names}")
        return archive.read(names[0]).decode("utf-8")


def load_all_texts(directory: str) -> dict:
    """Load every acquired CSV text keyed for the census pipeline."""
    out = {"spot_1h": [], "perp_1h": [], "funding": [], "metrics": []}
    base = directory
    for key, sub, prefix in (
        ("spot_1h", "spot_klines_1h", "BTCUSDT-1h-"),
        ("perp_1h", "futures_klines_1h", "BTCUSDT-1h-"),
        ("funding", "funding_rate", "BTCUSDT-fundingRate-"),
        ("metrics", "metrics", "BTCUSDT-metrics-"),
    ):
        folder = os.path.join(base, sub)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name.startswith(prefix) and name.endswith(".zip"):
                out[key].append(read_csv_from_zip(os.path.join(folder, name)))
    return out
