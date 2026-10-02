"""Inventory 2025 BTC/ETH Binance USD-M aggregate-trade objects and sizes.

S3 listing is source availability only. It does not validate each ZIP's
contents or imply a point-in-time signal or return.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

from research.futures.archive_catalog import ENDPOINT, NS

SYMBOLS = ("BTCUSDT", "ETHUSDT")
YEAR = 2025


def list_objects(prefix: str) -> dict[str, int]:
    query = urllib.parse.urlencode({"list-type": "2", "prefix": prefix, "max-keys": "1000"})
    request = urllib.request.Request(ENDPOINT + "?" + query,
                                     headers={"User-Agent": "rocket-research-inventory/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())
    if root.tag != f"{{{NS['s3']}}}ListBucketResult" or root.findtext(
            "s3:IsTruncated", namespaces=NS) == "true":
        raise ValueError("unexpected or truncated S3 object listing")
    objects = {}
    for item in root.findall("s3:Contents", NS):
        key = item.findtext("s3:Key", namespaces=NS)
        size = item.findtext("s3:Size", namespaces=NS)
        if key is None or size is None or key in objects:
            raise ValueError("bad S3 object metadata")
        objects[key] = int(size)
    return objects


def inventory() -> dict:
    result = {}
    expected_days = [(date(YEAR, 1, 1) + timedelta(days=i)).isoformat()
                     for i in range(365)]
    for symbol in SYMBOLS:
        prefix = f"data/futures/um/daily/aggTrades/{symbol}/{symbol}-aggTrades-{YEAR}"
        objects = list_objects(prefix)
        pattern = re.compile(re.escape(prefix) + r"-(\d{2}-\d{2})\.zip(\.CHECKSUM)?$")
        files = {}
        for key, size in objects.items():
            match = pattern.fullmatch(key)
            if match is None:
                raise ValueError(f"unexpected object: {key}")
            day = f"{YEAR}-{match.group(1)}"
            kind = "checksum" if match.group(2) else "zip"
            if day not in expected_days or kind in files.setdefault(day, {}):
                raise ValueError(f"duplicate or out-of-year object: {key}")
            files[day][kind] = size
        if sorted(files) != expected_days or any(set(item) != {"zip", "checksum"}
                                                  for item in files.values()):
            raise ValueError(f"incomplete daily archive inventory: {symbol}")
        result[symbol] = {"days": len(files),
                          "compressed_zip_bytes": sum(item["zip"] for item in files.values()),
                          "files": files}
    return {"scope": "2025 BTC/ETH aggregate-trade S3 object presence and size only",
            "symbols": result}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = inventory()
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({symbol: {key: value for key, value in data.items() if key != "files"}
                      for symbol, data in report["symbols"].items()}, indent=2))


if __name__ == "__main__":
    main()
