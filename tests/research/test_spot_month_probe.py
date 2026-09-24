from __future__ import annotations

import io
import zipfile

import pytest

from research.futures.spot_month_probe import DAY_MS, parse_daily_rows


def archive(stamps: list[int], *, divisor: int, zero_volume: bool = False,
            shortened_last: bool = False) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as zipped:
        lines = []
        for index, stamp in enumerate(stamps):
            volume = "0" if zero_volume else "10"
            quote = "0" if zero_volume else "1050"
            duration = 3_600_000 if shortened_last and index == len(stamps) - 1 else DAY_MS
            lines.append(f"{stamp * divisor},100,110,90,105,{volume},"
                         f"{(stamp + duration) * divisor - 1},{quote},1,0,0,0")
        zipped.writestr("sample.csv", "\n".join(lines) + "\n")
    return output.getvalue()


@pytest.mark.parametrize("year,divisor,first", [
    (2024, 1, 1704067200000),
    (2025, 1000, 1735689600000),
])
def test_spot_daily_timestamp_units_and_tradability(year: int, divisor: int, first: int) -> None:
    rows = parse_daily_rows(archive([first, first + DAY_MS], divisor=divisor), year)
    assert [row[0] for row in rows] == [first, first + DAY_MS]
    assert all(row[-1] == 1 for row in rows)
    empty = parse_daily_rows(archive([first], divisor=divisor, zero_volume=True), year)
    assert empty[0][-1] == 0


def test_spot_daily_accepts_early_microseconds_and_retains_gap_or_partial_day() -> None:
    first = 1735689600000
    early = parse_daily_rows(archive([1727740800000], divisor=1000), 2024)
    assert early[0][0] == 1727740800000
    with pytest.raises(ValueError, match="timestamp units"):
        parse_daily_rows(archive([first], divisor=100), 2025)
    rows = parse_daily_rows(archive([first, first + 2 * DAY_MS], divisor=1000,
                                    shortened_last=True), 2025)
    assert len(rows) == 2
    assert rows[-1][-2:] == (0, 0)
