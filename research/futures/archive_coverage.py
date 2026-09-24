"""Inventory monthly USD-M daily candle and funding files for paired symbols.

The resulting manifest describes archive availability, not historical trading
eligibility. No future file existence is used in a decision rule.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from research.futures.archive_catalog import ENDPOINT, NS, ROOT


def list_keys(prefix: str, *, timeout: float = 20.0) -> list[str]:
    keys: list[str] = []
    token: str | None = None
    seen: set[str] = set()
    while True:
        query = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            query["continuation-token"] = token
        request = urllib.request.Request(
            ENDPOINT + "?" + urllib.parse.urlencode(query),
            headers={"User-Agent": "rocket-research-inventory/1"},
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = response.read()
                break
            except (OSError, TimeoutError):
                if attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
        root = ET.fromstring(raw)
        if root.tag != f"{{{NS['s3']}}}ListBucketResult":
            raise ValueError("unexpected archive listing response")
        keys.extend(node.text or "" for node in root.findall("s3:Contents/s3:Key", NS))
        truncated = root.findtext("s3:IsTruncated", namespaces=NS) == "true"
        next_token = root.findtext("s3:NextContinuationToken", namespaces=NS)
        if not truncated:
            return keys
        if not next_token or next_token in seen:
            raise ValueError("invalid archive listing pagination")
        seen.add(next_token)
        token = next_token


def months_for(symbol: str, kind: str, *, timeout: float = 20.0) -> list[str]:
    if kind == "klines":
        prefix = f"{ROOT}klines/{symbol}/1d/"
        name = rf"{re.escape(symbol)}-1d-(\d{{4}}-\d{{2}})\.zip"
    elif kind == "fundingRate":
        prefix = f"{ROOT}fundingRate/{symbol}/"
        name = rf"{re.escape(symbol)}-fundingRate-(\d{{4}}-\d{{2}})\.zip"
    else:
        raise ValueError(kind)
    pattern = re.compile(re.escape(prefix) + name + r"$")
    months = [match.group(1) for key in list_keys(prefix, timeout=timeout)
              if (match := pattern.fullmatch(key))]
    if len(months) != len(set(months)):
        raise ValueError(f"duplicate archive month for {symbol} {kind}")
    return sorted(months)


def inventory(symbols: list[str], *, workers: int = 16) -> dict[str, dict[str, list[str]]]:
    results: dict[str, dict[str, list[str]]] = {symbol: {} for symbol in symbols}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(months_for, symbol, kind): (symbol, kind)
                for symbol in symbols for kind in ("klines", "fundingRate")}
        for future in as_completed(jobs):
            symbol, kind = jobs[future]
            results[symbol][kind] = future.result()
    return dict(sorted(results.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path, help="JSON from archive_catalog.py")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text())
    symbols = [symbol for symbol in catalog["paired_symbols"] if symbol.endswith("USDT")]
    print(json.dumps({
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source": ENDPOINT,
        "meaning": "monthly file presence only; NOT PIT eligibility",
        "symbols": inventory(symbols, workers=args.workers),
    }, indent=2))


if __name__ == "__main__":
    main()
