"""Audit two fixed Binance USD-M aggregate-trade days without scoring returns.

Input ZIPs and official CHECKSUM files are cached locally. The report only
records schema, integrity and timestamp/order coverage, not price outcomes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

SYMBOLS = ("BTCUSDT", "ETHUSDT")
DAY = "2025-01-01"
COLUMNS = ("agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id",
           "transact_time", "is_buyer_maker")
START_MS = 1_735_689_600_000
END_MS = START_MS + 86_400_000


def audit_one(directory: Path, symbol: str) -> dict:
    name = f"{symbol}-aggTrades-{DAY}.zip"
    path = directory / name
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    checksum = (directory / f"{name}.CHECKSUM").read_text().split()
    if len(checksum) != 2 or checksum != [digest, name]:
        raise ValueError(f"official checksum mismatch: {name}")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.namelist() != [name.removesuffix(".zip") + ".csv"]:
            raise ValueError(f"unexpected ZIP layout: {name}")
        with archive.open(archive.namelist()[0]) as handle:
            reader = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig"))
            if tuple(reader.fieldnames or ()) != COLUMNS:
                raise ValueError(f"unexpected aggregate-trade schema: {name}")
            count = 0
            first_ms = last_ms = first_id = last_id = None
            prev_ms = prev_id = None
            disorder = id_gaps = nonpositive_qty = 0
            sides = {"true": 0, "false": 0}
            minutes = set()
            for row in reader:
                stamp = int(row["transact_time"])
                agg_id = int(row["agg_trade_id"])
                if not START_MS <= stamp < END_MS:
                    raise ValueError(f"out-of-day trade: {name}")
                if row["is_buyer_maker"] not in sides:
                    raise ValueError(f"unrecognized taker-side flag: {name}")
                if float(row["price"]) <= 0:
                    raise ValueError(f"nonpositive trade price: {name}")
                if float(row["quantity"]) <= 0:
                    nonpositive_qty += 1
                if int(row["first_trade_id"]) > int(row["last_trade_id"]):
                    raise ValueError(f"reversed underlying trade IDs: {name}")
                if prev_ms is not None:
                    disorder += stamp < prev_ms or agg_id <= prev_id
                    id_gaps += agg_id != prev_id + 1
                first_ms = stamp if first_ms is None else first_ms
                first_id = agg_id if first_id is None else first_id
                last_ms, last_id = stamp, agg_id
                prev_ms, prev_id = stamp, agg_id
                minutes.add(stamp // 60_000)
                sides[row["is_buyer_maker"]] += 1
                count += 1
    return {"source_key": name, "sha256": digest, "rows": count,
            "first_ms": first_ms, "last_ms": last_ms,
            "first_agg_id": first_id, "last_agg_id": last_id,
            "distinct_minutes": len(minutes), "out_of_order_pairs": disorder,
            "nonconsecutive_agg_id_pairs": id_gaps,
            "nonpositive_quantity_rows": nonpositive_qty,
            "buyer_maker_flag_counts": sides}


def audit(directory: Path) -> dict:
    report = {"scope": "fixed 2025-01-01 BTC/ETH aggregate-trade source sample; no returns",
              "results": [audit_one(directory, symbol) for symbol in SYMBOLS]}
    (directory / "source_probe.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.directory), indent=2))


if __name__ == "__main__":
    main()
