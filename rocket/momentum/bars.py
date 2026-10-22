"""Binance archive ingest and 4h aggregation. Deterministic, read-only.

Raw source bytes -> validated 1h rows -> UTC 4h bars. Every row carries
event_time / available_at (assumed bar_end + 5m retrospectively) /
vintage / ingested_at. 4h bars cover [open, open+4h); a bar is complete
only at its boundary.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import zipfile
from datetime import UTC, datetime, timedelta

from rocket.momentum import contracts

MS_UNIT = 1_000
US_UNIT = 1_000_000
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

ASSUMED_AVAILABILITY_LAG = timedelta(seconds=contracts.DECISION_LAG_SECONDS)


def _to_ms(raw: int) -> tuple[int, str]:
    """Normalize a vendor timestamp to epoch milliseconds.

    Binance spot archives used milliseconds, then microseconds (2025+).
    Magnitude discriminates: microsecond stamps are ~1000x larger.
    Returns (ms, unit) where unit is 'ms' or 'us'.
    """
    magnitude = abs(int(raw))
    # No realistic millisecond stamp reaches 1e15 (year 33658); every
    # microsecond archive stamp exceeds it. Small synthetic values are ms.
    if magnitude >= 10**15:  # microseconds (close stamps end at ...999us).
        return magnitude // 1000, "us"
    return magnitude, "ms"


def ms_to_iso(ms: int) -> str:
    return (_EPOCH + timedelta(milliseconds=int(ms))).isoformat()


def _check_kline_row(lineno: int, fields: list[str]) -> dict:
    """Validate one raw CSV row; raises ValueError with the reason."""
    if len(fields) < 11:
        raise ValueError(f"kline line {lineno}: expected >=11 fields, got {len(fields)}")
    try:
        open_raw = int(float(fields[0]))
        close_raw = int(float(fields[6]))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"kline line {lineno}: bad timestamps") from exc
    open_ms, unit = _to_ms(open_raw)
    close_ms, close_unit = _to_ms(close_raw)
    if close_unit != unit:
        raise ValueError(f"kline line {lineno}: mixed timestamp units")
    if open_ms % (3600 * 1000) != 0:
        raise ValueError(f"kline line {lineno}: 1h open not hour-aligned")
    # close = open + 1h - 1 unit in both units (3599999 ms either way).
    if close_ms != open_ms + 3600 * 1000 - 1:
        raise ValueError(
            f"kline line {lineno}: close_time != open+1h-1unit "
            f"(open_ms={open_ms} close_ms={close_ms} unit={unit})"
        )
    return {"open_ms": open_ms, "close_ms": close_ms, "unit": unit}


def parse_kline_csv(
    text: str, *, vintage: str, ingested_at: str, quarantine: list | None = None
) -> list[dict]:
    """Parse one Binance kline CSV (no header, 12 fields).

    Invalid rows are quarantined (recorded in the caller's list, default a
    throwaway) and skipped, never imputed: downstream gaps yield UNKNOWN
    decisions. Callers must report quarantine counts.
    """
    if quarantine is None:
        quarantine = []
    rows: list[dict] = []
    reader = csv.reader(io.StringIO(text))
    for lineno, fields in enumerate(reader, start=1):
        if not fields or all(not f.strip() for f in fields):
            continue
        try:
            checked = _check_kline_row(lineno, fields)
        except ValueError as exc:
            quarantine.append({"lineno": lineno, "reason": str(exc),
                               "raw": ",".join(fields)[:200], "vintage": vintage})
            continue
        open_ms, close_ms, unit = checked["open_ms"], checked["close_ms"], checked["unit"]
        try:
            record = {
                "open_ms": open_ms,
                "open_time": ms_to_iso(open_ms),
                "close_ms": close_ms,
                "open": float(fields[1]),
                "high": float(fields[2]),
                "low": float(fields[3]),
                "close": float(fields[4]),
                "volume": float(fields[5]),
                "close_time": ms_to_iso(close_ms),
                "quote_volume": float(fields[7]),
                "trades": int(float(fields[8])),
                "taker_base_volume": float(fields[9]),
                "taker_quote_volume": float(fields[10]),
                "timestamp_unit": unit,
                "vintage": vintage,
                "ingested_at": ingested_at,
            }
        except (TypeError, ValueError) as exc:
            quarantine.append({"lineno": lineno,
                               "reason": f"kline line {lineno}: bad numeric field: {exc}",
                               "raw": ",".join(fields)[:200], "vintage": vintage})
            continue
        if not all(math.isfinite(record[k]) for k in ("open", "high", "low", "close")):
            quarantine.append({"lineno": lineno, "reason": f"kline line {lineno}: non-finite OHLC",
                               "raw": ",".join(fields)[:200], "vintage": vintage})
            continue
        if min(record["open"], record["high"], record["low"], record["close"]) <= 0:
            quarantine.append({"lineno": lineno, "reason": f"kline line {lineno}: non-positive price",
                               "raw": ",".join(fields)[:200], "vintage": vintage})
            continue
        if record["high"] < record["low"]:
            quarantine.append({"lineno": lineno, "reason": f"kline line {lineno}: high < low",
                               "raw": ",".join(fields)[:200], "vintage": vintage})
            continue
        # available_at is an assumed reconstruction (bar_end + 5m), never a
        # claim of recorded historical receipt.
        end = _EPOCH + timedelta(milliseconds=open_ms + 3600 * 1000)
        record["event_time"] = ms_to_iso(open_ms)
        record["available_at"] = (end + ASSUMED_AVAILABILITY_LAG).isoformat()
        rows.append(record)
    rows.sort(key=lambda r: r["open_ms"])
    return rows


def read_monthly_zip(path: str, *, vintage: str, ingested_at: str) -> list[dict]:
    """Read the single CSV inside a monthly archive zip."""
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"{path}: expected 1 csv, found {names}")
        text = archive.read(names[0]).decode("utf-8")
    return parse_kline_csv(text, vintage=vintage, ingested_at=ingested_at)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(path: str, checksum_text: str) -> str:
    """checksum_text is the upstream .CHECKSUM file content ('<sha>  <name>')."""
    expected = checksum_text.strip().split()[0]
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"{path}: checksum mismatch {actual} != {expected}")
    return actual


def aggregate_4h(rows_1h: list[dict]) -> list[dict]:
    """Aggregate contiguous 1h rows into complete UTC 4h bars.

    A 4h bar covering [T, T+4h) requires all four constituent 1h opens.
    Incomplete groups are dropped (gap), never imputed.
    """
    by_open = {r["open_ms"]: r for r in rows_1h}
    if not by_open:
        return []
    hour_ms = 3600 * 1000
    first = min(by_open) // (4 * hour_ms) * (4 * hour_ms)
    last = max(by_open)
    bars: list[dict] = []
    cursor = first
    while cursor + 4 * hour_ms - 1 <= last or cursor <= last:
        members = [by_open.get(cursor + i * hour_ms) for i in range(4)]
        if all(m is not None for m in members):
            assert all(m is not None for m in members)
            members_t = [m for m in members if m is not None]
            end = cursor + 4 * hour_ms
            bars.append(
                {
                    "open_ms": cursor,
                    "open_time": ms_to_iso(cursor),
                    "event_time": ms_to_iso(cursor),
                    "available_at": (
                        _EPOCH + timedelta(milliseconds=end) + ASSUMED_AVAILABILITY_LAG
                    ).isoformat(),
                    "open": members_t[0]["open"],
                    "high": max(m["high"] for m in members_t),
                    "low": min(m["low"] for m in members_t),
                    "close": members_t[3]["close"],
                    "volume": sum(m["volume"] for m in members_t),
                    "quote_volume": sum(m["quote_volume"] for m in members_t),
                    "trades": sum(m["trades"] for m in members_t),
                    "complete": True,
                    "vintage": members_t[0]["vintage"],
                    "ingested_at": members_t[0]["ingested_at"],
                }
            )
        cursor += 4 * hour_ms
        if cursor > last:
            break
    return bars


def contiguous_4h_before(
    bars_4h: list[dict],
    cutoff_ms: int,
    *,
    days: int = contracts.HISTORY_DAYS_REQUIRED,
    min_bars: int = 0,
    by_open: dict | None = None,
) -> list[dict]:
    """Return the trailing contiguous 4h run ending exactly at cutoff_ms.

    Empty (not partial) when any bar is missing: callers emit UNKNOWN.
    min_bars raises the requirement above the day count (sigma needs 181
    closes = 30d + one bar; the day rule is then subsumed, never relaxed).
    Pass a prebuilt by_open map in scans; otherwise one is built per call.
    """
    step = 4 * 3600 * 1000
    need = max(int(days * 24 * 3600 * 1000 / step), min_bars)
    if by_open is None:
        by_open = {b["open_ms"]: b for b in bars_4h}
    run: list[dict] = []
    cursor = cutoff_ms - step
    for _ in range(need):
        bar = by_open.get(cursor)
        if bar is None:
            return []
        run.append(bar)
        cursor -= step
    run.reverse()
    return run
