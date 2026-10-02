"""Inspect minute trade and index archives around unresolved FUT-001 outcomes.

This produces settlement *candidates*, not an accepted event calendar. Official
dated notices and exact index averaging must be checked before outcome repair.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.parse
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from research.futures.download_archives import BASE, fetch
from research.futures.normalize_archives import DAY_MS

MINUTE_MS = 60_000


def minute_key(symbol: str, month: str, kind: str) -> str:
    if kind not in ("klines", "indexPriceKlines"):
        raise ValueError(kind)
    return f"data/futures/um/monthly/{kind}/{symbol}/1m/{symbol}-1m-{month}.zip"


def verified_csv(key: str, output: Path) -> tuple[list[list[str]], str]:
    url = BASE + urllib.parse.quote(key, safe="/")
    expected, name = fetch(url + ".CHECKSUM").decode("utf-8").split()[:2]
    if name != Path(key).name:
        raise ValueError(f"checksum filename mismatch: {key}")
    raw = fetch(url)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected.lower():
        raise ValueError(f"checksum mismatch: {key}")
    path = output / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != 1:
            raise ValueError(f"unexpected ZIP members: {key}")
        rows = list(csv.reader(io.TextIOWrapper(archive.open(names[0]), encoding="utf-8-sig")))
    if rows and rows[0][0] == "open_time":
        rows = rows[1:]
    return rows, digest


def issue_months(preflight: dict) -> list[tuple[str, str]]:
    months = set()
    for issue in preflight["unresolved_exposures"]:
        stamp = datetime.fromtimestamp(issue["entry_ms"] / 1000, UTC)
        months.add((issue["symbol"], stamp.strftime("%Y-%m")))
        if stamp.day <= 2:
            prior = datetime.fromtimestamp((issue["entry_ms"] - 2 * DAY_MS) / 1000, UTC)
            months.add((issue["symbol"], prior.strftime("%Y-%m")))
    return sorted(months)


def probe_one(symbol: str, month: str, output: Path) -> dict:
    data = {"symbol": symbol, "month": month}
    for kind in ("klines", "indexPriceKlines"):
        key = minute_key(symbol, month, kind)
        rows, digest = verified_csv(key, output)
        data[kind + "_key"] = key
        data[kind + "_sha256"] = digest
        data[kind + "_rows"] = len(rows)
        if kind == "klines":
            active = [row for row in rows if float(row[5]) > 0]
            if active:
                data["last_active_minute_ms"] = int(active[-1][0])
                data["last_active_close"] = float(active[-1][4])
                data["post_active_rows"] = len(rows) - rows.index(active[-1]) - 1
        else:
            index_by_minute = {int(row[0]): float(row[4]) for row in rows}
            data["index_by_minute"] = index_by_minute
    last = data.get("last_active_minute_ms")
    if last is not None:
        index = data.pop("index_by_minute")
        for duration in (30, 60):
            values = [index.get(last - step * MINUTE_MS) for step in range(1, duration + 1)]
            data[f"index_mean_{duration}m_before_last_active"] = (
                sum(values) / duration if all(value is not None for value in values) else None)
    else:
        data.pop("index_by_minute", None)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preflight", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    issues = issue_months(json.loads(args.preflight.read_text()))
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe_one, symbol, month, args.output_root): (symbol, month)
                   for symbol, month in issues}
        for future in as_completed(futures):
            symbol, month = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"symbol": symbol, "month": month, "error": str(exc)})
    report = {"retrieved_at": datetime.now(UTC).isoformat(),
              "meaning": "minute-archive coverage and settlement candidates; NOT accepted exits",
              "results": sorted(results, key=lambda item: (item["symbol"], item["month"]))}
    path = args.output_root / "settlement_probe.json"
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({"issues": len(issues),
                      "success": sum("error" not in item for item in results),
                      "failed": sum("error" in item for item in results),
                      "report": str(path)}, indent=2))


if __name__ == "__main__":
    main()
