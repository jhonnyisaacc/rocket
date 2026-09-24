"""Audit CME BTC legacy COT coverage with conservative publication timestamps.

Reads cached official annual ZIPs. This is a source-only audit: no trading
signal, price alignment or forward return is computed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

YEARS = range(2020, 2026)
CODE = "133741"
FIELDS = ("Market and Exchange Names", "As of Date in Form YYYY-MM-DD",
          "CFTC Contract Market Code", "Open Interest (All)",
          "Noncommercial Positions-Long (All)", "Noncommercial Positions-Short (All)",
          "Nonreportable Positions-Long (All)", "Nonreportable Positions-Short (All)",
          " Total Reportable Positions-Long (All)",
          "Total Reportable Positions-Short (All)")

# Actual exceptional publication dates from CFTC Historical Special Announcements.
# The 2025 map uses its amended 2025-12-09 schedule, not the superseded one.
EXCEPTION_RELEASES = {
    "2023-01-31": "2023-02-24", "2023-02-07": "2023-03-03",
    "2023-02-14": "2023-03-08", "2023-02-21": "2023-03-10",
    "2023-02-28": "2023-03-14", "2023-03-07": "2023-03-16",
    "2023-03-14": "2023-03-21", "2025-01-07": "2025-01-13",
    "2025-09-30": "2025-11-19", "2025-10-07": "2025-11-21",
    "2025-10-14": "2025-11-25", "2025-10-21": "2025-12-02",
    "2025-10-28": "2025-12-05", "2025-11-04": "2025-12-09",
    "2025-11-10": "2025-12-10", "2025-11-18": "2025-12-12",
    "2025-11-25": "2025-12-15", "2025-12-02": "2025-12-17",
    "2025-12-09": "2025-12-19", "2025-12-16": "2025-12-23",
    "2025-12-23": "2025-12-29",
}


def available_date(asof: date) -> date:
    """Earliest allowed UTC midnight for a decision using this report.

    Standard releases occur Friday 15:30 Eastern after Tuesday positions.
    Ten calendar days from as-of conservatively covers ordinary holidays.
    Exceptional releases become eligible no sooner than the following day.
    """
    ordinary = asof + timedelta(days=10)
    exceptional = EXCEPTION_RELEASES.get(asof.isoformat())
    return max(ordinary, date.fromisoformat(exceptional) + timedelta(days=1)) if exceptional else ordinary


def audit(directory: Path) -> dict:
    files = []
    records = []
    for year in YEARS:
        path = directory / f"deacot{year}.zip"
        raw = path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if archive.namelist() != ["annual.txt"]:
                raise ValueError(f"unexpected CFTC archive layout: {path.name}")
            with archive.open("annual.txt") as handle:
                reader = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig"))
                if not set(FIELDS).issubset(reader.fieldnames or []):
                    raise ValueError(f"missing CFTC columns: {path.name}")
                selected = [row for row in reader if row["CFTC Contract Market Code"] == CODE]
        if not selected:
            raise ValueError(f"BTC contract missing: {path.name}")
        for row in selected:
            asof = date.fromisoformat(row["As of Date in Form YYYY-MM-DD"])
            if asof.year != year or "BITCOIN - CHICAGO MERCANTILE EXCHANGE" != row[
                    "Market and Exchange Names"]:
                raise ValueError(f"unexpected BTC market/date: {path.name}")
            interest = int(row["Open Interest (All)"])
            long = int(row["Nonreportable Positions-Long (All)"])
            short = int(row["Nonreportable Positions-Short (All)"])
            speculative_long = int(row["Noncommercial Positions-Long (All)"])
            speculative_short = int(row["Noncommercial Positions-Short (All)"])
            reportable_long = int(row[" Total Reportable Positions-Long (All)"])
            reportable_short = int(row["Total Reportable Positions-Short (All)"])
            if interest <= 0 or speculative_long + speculative_short <= 0 or min(
                    long, short, speculative_long, speculative_short,
                    reportable_long, reportable_short) < 0:
                raise ValueError(f"invalid BTC positioning: {asof}")
            if interest != long + reportable_long or interest != short + reportable_short:
                raise ValueError(f"COT position totals disagree: {asof}")
            records.append({"asof": asof.isoformat(),
                            "available_utc_date": available_date(asof).isoformat(),
                            "year": year})
        files.append({"source_key": path.name, "sha256": hashlib.sha256(raw).hexdigest(),
                      "btc_rows": len(selected)})
    records.sort(key=lambda item: item["asof"])
    dates = [date.fromisoformat(item["asof"]) for item in records]
    if len(dates) != len(set(dates)) or dates != sorted(dates):
        raise ValueError("duplicate or misordered BTC report dates")
    missing_exceptions = set(EXCEPTION_RELEASES) - {item["asof"] for item in records}
    if missing_exceptions:
        raise ValueError(f"exceptional reports absent: {sorted(missing_exceptions)}")
    gaps = [(right - left).days for left, right in zip(dates, dates[1:])]
    report = {"scope": "CME BTC legacy COT futures-only 2020-2025 source and release audit",
              "contract_code": CODE, "files": files, "total_reports": len(records),
              "first_asof": records[0]["asof"], "last_asof": records[-1]["asof"],
              "max_asof_gap_days": max(gaps),
              "nonseven_day_asof_gaps": sum(gap != 7 for gap in gaps),
              "exceptional_report_count": len(EXCEPTION_RELEASES),
              "records": records}
    (directory / "source_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    report = audit(args.directory)
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))


if __name__ == "__main__":
    main()
