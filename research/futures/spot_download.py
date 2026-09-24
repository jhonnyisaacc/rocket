"""Resumable checksum-verified acquisition of monthly Binance spot 1d ZIPs.

Run with the JSON from spot_month_inventory.py. Raw files and the append-only
acquisition log belong in an ignored local directory outside the PR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from research.futures.download_archives import BASE, fetch
from research.futures.spot_source_audit import SPOT_ROOT


def spot_key(symbol: str, month: str) -> str:
    return f"{SPOT_ROOT}{symbol}/1d/{symbol}-1d-{month}.zip"


def verified_spot(symbol: str, month: str) -> tuple[bytes, dict]:
    key = spot_key(symbol, month)
    url = BASE + urllib.parse.quote(key, safe="/")
    checksum_text = fetch(url + ".CHECKSUM").decode("utf-8").strip().split()
    if len(checksum_text) != 2 or checksum_text[1] != Path(key).name:
        raise ValueError(f"malformed checksum: {key}")
    expected = checksum_text[0].lower()
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise ValueError(f"invalid checksum digest: {key}")
    raw = fetch(url)
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise ValueError(f"checksum mismatch: {key}")
    return raw, {"key": key, "symbol": symbol, "month": month,
                 "source": url, "checksum_source": url + ".CHECKSUM",
                 "sha256": actual, "bytes": len(raw),
                 "retrieved_at": datetime.now(UTC).isoformat()}


def acquire(inventory: dict, output: Path, *, workers: int = 32) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "acquisition.jsonl"
    existing = {}
    if log_path.exists():
        for line in log_path.read_text().splitlines():
            record = json.loads(line)
            existing[record["key"]] = record
    tasks = [(symbol, month) for symbol, months in sorted(inventory["spot_months"].items())
             for month in months]
    pending = []
    for symbol, month in tasks:
        key = spot_key(symbol, month)
        path = output / key
        record = existing.get(key)
        if record and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]:
            continue
        pending.append((symbol, month))
    lock = threading.Lock()
    failures = []
    done = 0

    def one(task: tuple[str, str]) -> None:
        nonlocal done
        raw, record = verified_spot(*task)
        path = output / record["key"]
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + f".{threading.get_ident()}.tmp")
        temp.write_bytes(raw)
        os.replace(temp, path)
        with lock:
            with log_path.open("a") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
            done += 1
            if done % 500 == 0:
                print(f"verified {done}/{len(pending)} spot archives", file=sys.stderr, flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(one, task): task for task in pending}
        for future in as_completed(jobs):
            try:
                future.result()
            except Exception as exc:
                failures.append({"task": jobs[future], "error": str(exc)})
    summary = {"tasks": len(tasks), "already_verified": len(tasks) - len(pending),
               "newly_verified": done, "failures": failures}
    (output / "acquisition_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()
    summary = acquire(json.loads(args.inventory.read_text()), args.output, workers=args.workers)
    print(json.dumps(summary, indent=2))
    if summary["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
