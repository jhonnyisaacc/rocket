"""Verified BTC spot archives. Receipt assumptions are explicit; bytes never revised in place."""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

from rocket.momentum.core import HOUR, LAG, Bar, aggregate_four_hours, fingerprint

BASE = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h"


def parse_archive(data: bytes, year: int, month: int, ingested: int, rejected=None) -> list[Bar]:
    start = int(datetime(year, month, 1, tzinfo=UTC).timestamp() * 1000)
    factor = 1000 if year >= 2025 else 1
    bars = []
    rejected = [] if rejected is None else rejected
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        expected = f"BTCUSDT-1h-{year}-{month:02d}.csv"
        if archive.namelist() != [expected]:
            raise ValueError("unexpected ZIP member")
        for row in csv.reader(io.StringIO(archive.read(expected).decode("utf-8-sig"))):
            if len(row) != 12:
                raise ValueError("unexpected archive columns")
            opening, closing = int(row[0]), int(row[6])
            if (
                opening % (HOUR * factor)
                or opening < start * factor
                or opening >= (start + calendar.monthrange(year, month)[1] * 24 * HOUR) * factor
                or (bars and opening // factor <= bars[-1].open_time)
            ):
                raise ValueError("hourly ordering/alignment/timestamp unit mismatch")
            if closing != opening + HOUR * factor - 1:
                rejected.append(
                    {
                        "open_time": opening // factor,
                        "vendor_close_time": closing,
                        "reason": "NONSTANDARD_CLOSE_TIMESTAMP",
                        "raw_row_sha256": fingerprint(row),
                    }
                )
                continue
            bars.append(
                Bar(
                    opening // factor,
                    opening // factor + HOUR,
                    opening // factor + HOUR + LAG,
                    ingested,
                    *map(float, row[1:6]),
                )
            )
    if not bars:
        raise ValueError("empty month")
    return bars


def acquire_month(root: Path, year: int, month: int):
    name = f"BTCUSDT-1h-{year}-{month:02d}.zip"
    target = root / name
    sidecar = root / (name + ".CHECKSUM")
    receipt = root / (name + ".receipt.json")
    if not target.exists():

        def get(suffix):
            req = urllib.request.Request(
                f"{BASE}/{name}{suffix}", headers={"User-Agent": "rocket-momentum-research/1"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read()

        checksum = get(".CHECKSUM")
        raw = get("")
        digest, stated_name = checksum.decode().split()
        if digest != hashlib.sha256(raw).hexdigest() or stated_name != name:
            raise ValueError("source checksum mismatch")
        # Exclusive creation prevents a refresh from silently changing the research data.
        with target.open("xb") as handle:
            handle.write(raw)
        sidecar.write_bytes(checksum)
        receipt.write_text(
            json.dumps(
                {
                    "ingested_at": int(datetime.now(UTC).timestamp() * 1000),
                    "source": f"{BASE}/{name}",
                }
            )
            + "\n"
        )
    raw = target.read_bytes()
    digest, stated_name = sidecar.read_text().split()
    if digest != hashlib.sha256(raw).hexdigest() or stated_name != name:
        raise ValueError("cached checksum mismatch")
    ingested = json.loads(receipt.read_text())["ingested_at"]
    rejected = []
    bars = parse_archive(raw, year, month, ingested, rejected)
    return bars, {
        "file": name,
        "sha256": digest,
        "rows": len(bars),
        "ingested_at": ingested,
        "url": f"{BASE}/{name}",
        "rejected_rows": rejected,
    }


def acquire(root: Path, report: Path):
    root.mkdir(parents=True, exist_ok=True)
    months = [(y, m) for y in range(2019, 2026) for m in range(1, 13)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        bundles = list(pool.map(lambda ym: acquire_month(root, *ym), months))
    hourly = [b for bars, _ in bundles for b in bars]
    audit = {
        "source": "Binance BTCUSDT spot 1h archives",
        "years": [2019, 2025],
        "availability": "RECONSTRUCTED_ASSUMED_END_PLUS_5M",
        "vintage": "CURRENT_ARCHIVE_NOT_ORIGINAL_RECEIPT",
        "hourly_rows": len(hourly),
        "four_hour_rows": len(aggregate_four_hours(hourly)),
        "missing_hours": sum((b.open_time - a.end_time) // HOUR for a, b in pairwise(hourly)),
        "gap_intervals": [
            {"start": a.end_time, "end": b.open_time}
            for a, b in pairwise(hourly)
            if b.open_time != a.end_time
        ],
        "files": [meta for _, meta in bundles],
    }
    audit["manifest_sha256"] = fingerprint(audit)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(audit, indent=2) + "\n")
    return hourly


def load(root: Path):
    return [
        b for y in range(2019, 2026) for m in range(1, 13) for b in acquire_month(root, y, m)[0]
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    rows = acquire(args.root, args.manifest)
    print(f"Verified {len(rows)} BTC hourly observations; no predictive outcomes scored.")
