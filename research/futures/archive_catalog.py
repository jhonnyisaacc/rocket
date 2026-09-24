"""Read-only inventory of Binance USD-M monthly kline archive directories.

This is a coverage inventory, not an eligibility or listing-date source.
Run: python research/futures/archive_catalog.py > /tmp/rocket-archive-catalog.json
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

ENDPOINT = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
PREFIX = "data/futures/um/monthly/klines/"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


def parse_page(raw: bytes) -> tuple[list[str], str | None]:
    root = ET.fromstring(raw)
    if root.tag != f"{{{NS['s3']}}}ListBucketResult":
        raise ValueError("unexpected archive listing response")
    prefixes = [
        node.text or ""
        for node in root.findall("s3:CommonPrefixes/s3:Prefix", NS)
    ]
    token = root.findtext("s3:NextContinuationToken", namespaces=NS)
    truncated = root.findtext("s3:IsTruncated", namespaces=NS) == "true"
    if truncated and not token:
        raise ValueError("truncated listing without continuation token")
    return prefixes, token if truncated else None


def list_contract_directories(*, timeout: float = 20.0) -> list[str]:
    symbols: set[str] = set()
    token: str | None = None
    seen_tokens: set[str] = set()
    while True:
        query = {"list-type": "2", "prefix": PREFIX, "delimiter": "/", "max-keys": "1000"}
        if token:
            query["continuation-token"] = token
        url = ENDPOINT + "?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, headers={"User-Agent": "rocket-research-inventory/1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            prefixes, next_token = parse_page(response.read())
        for prefix in prefixes:
            if not prefix.startswith(PREFIX) or not prefix.endswith("/"):
                raise ValueError(f"unexpected archive prefix: {prefix}")
            symbol = prefix[len(PREFIX) : -1]
            if not symbol or "/" in symbol:
                raise ValueError(f"unexpected contract directory: {prefix}")
            symbols.add(symbol)
        if next_token is None:
            break
        if next_token in seen_tokens:
            raise ValueError("repeated archive continuation token")
        seen_tokens.add(next_token)
        token = next_token
    return sorted(symbols)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    symbols = list_contract_directories(timeout=args.timeout)
    print(json.dumps({
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source": ENDPOINT,
        "prefix": PREFIX,
        "meaning": "archive directories only; NOT a historical tradable universe",
        "directory_count": len(symbols),
        "symbols": symbols,
    }, indent=2))


if __name__ == "__main__":
    main()
