"""Download and checksum monthly research archives; resumable and read-only upstream.

Run from the repository root with a coverage inventory JSON. Raw files and the
append-only acquisition log go to an ignored directory outside the PR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

BASE = "https://data.binance.vision/"
KINDS = ("klines", "fundingRate")


def archive_key(symbol: str, kind: str, month: str) -> str:
    if kind == "klines":
        return f"data/futures/um/monthly/klines/{symbol}/1d/{symbol}-1d-{month}.zip"
    if kind == "fundingRate":
        return f"data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{month}.zip"
    raise ValueError(kind)


def fetch(url: str, *, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "rocket-research-acquisition/1"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (OSError, TimeoutError, urllib.error.HTTPError):
            if attempt == 3:
                raise
            time.sleep(0.5 * (attempt + 1))
    raise AssertionError("unreachable")


def verified_archive(symbol: str, kind: str, month: str) -> tuple[bytes, dict]:
    key = archive_key(symbol, kind, month)
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
    return raw, {
        "key": key, "symbol": symbol, "kind": kind, "month": month,
        "source": url, "checksum_source": url + ".CHECKSUM",
        "sha256": actual, "bytes": len(raw), "retrieved_at": datetime.now(UTC).isoformat(),
    }


def tasks_from_coverage(coverage: dict, start_year: int, end_year: int,
                        selected: set[str] | None = None) -> list[tuple[str, str, str]]:
    tasks = []
    for symbol, by_kind in sorted(coverage["symbols"].items()):
        if selected is not None and symbol not in selected:
            continue
        for kind in KINDS:
            tasks.extend((symbol, kind, month) for month in by_kind[kind]
                         if start_year <= int(month[:4]) <= end_year)
    return tasks


def acquire(coverage: dict, output: Path, *, start_year: int, end_year: int,
            selected: set[str] | None = None, workers: int = 32) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "acquisition.jsonl"
    existing = {}
    if log_path.exists():
        for line in log_path.read_text().splitlines():
            record = json.loads(line)
            existing[record["key"]] = record
    tasks = tasks_from_coverage(coverage, start_year, end_year, selected)
    pending = []
    for symbol, kind, month in tasks:
        key = archive_key(symbol, kind, month)
        path = output / key
        record = existing.get(key)
        if record and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]:
            continue
        pending.append((symbol, kind, month))
    lock = threading.Lock()
    failures = []
    done = 0

    def one(task: tuple[str, str, str]) -> None:
        nonlocal done
        symbol, kind, month = task
        raw, record = verified_archive(symbol, kind, month)
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
                print(f"verified {done}/{len(pending)} archives", file=sys.stderr, flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, task): task for task in pending}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:  # preserve every failed key, then return nonzero
                failures.append({"task": futures[future], "error": str(exc)})
    summary = {"tasks": len(tasks), "already_verified": len(tasks)-len(pending),
               "newly_verified": done, "failures": failures}
    (output / "acquisition_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--symbols", help="comma-separated source-data probe; omit for all")
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()
    coverage = json.loads(args.coverage.read_text())
    selected = set(args.symbols.split(",")) if args.symbols else None
    summary = acquire(coverage, args.output, start_year=args.start_year,
                      end_year=args.end_year, selected=selected, workers=args.workers)
    print(json.dumps(summary, indent=2))
    if summary["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
