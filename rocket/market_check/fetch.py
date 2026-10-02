"""Build a cached daily panel from public sources. No API keys are written into code."""

from __future__ import annotations

import csv
import io
import sys
import time
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import orjson

from rocket.market_check.config import Config
from rocket.market_check.panel import SeriesPanel

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
TREASURY_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv"
)
EFFR_URL = "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"
DERIBIT = "https://www.deribit.com/api/v2/public"
YAHOO = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"

FRED_SERIES = {
    "wti_fred": "DCOILWTICO",
    "brent_fred": "DCOILBRENTEU",
    "vix_fred": "VIXCLS",
    "hy_oas": "BAMLH0A0HYM2",
    "ig_oas": "BAMLC0A0CM",
    "dollar_broad": "DTWEXBGS",
}


def _get(client: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(4):
        try:
            response = client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.HTTPError, httpx.StreamError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    assert last is not None
    raise last


def _cached(path: Path, loader) -> bytes:
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    payload = loader()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _quarters(start: date, end: date) -> list[tuple[date, date]]:
    rows = []
    cursor = date(start.year, ((start.month - 1) // 3) * 3 + 1, 1)
    while cursor <= end:
        nxt = date(cursor.year + 1, 1, 1) if cursor.month >= 10 else date(cursor.year, cursor.month + 3, 1)
        last = nxt - timedelta(days=1)
        rows.append((max(cursor, start), min(last, end)))
        cursor = nxt
    return rows


def _parse_fred(text: str) -> dict[str, float]:
    rows = {}
    for line in text.splitlines()[1:]:
        if "," not in line:
            continue
        stamp, raw = line.split(",", 1)
        raw = raw.strip()
        if raw in {"", "."}:
            continue
        try:
            rows[stamp[:10]] = float(raw)
        except ValueError:
            continue
    return rows


def _parse_yahoo(payload: dict[str, Any]) -> dict[str, float]:
    result = (payload.get("chart") or {}).get("result") or [None]
    block = result[0] or {}
    stamps = block.get("timestamp") or []
    quote = ((block.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    adjusted = (((block.get("indicators") or {}).get("adjclose") or [{}])[0] or {}).get("adjclose") or []
    rows = {}
    for index, stamp in enumerate(stamps):
        value = None
        if index < len(adjusted) and adjusted[index] is not None:
            value = adjusted[index]
        elif index < len(closes) and closes[index] is not None:
            value = closes[index]
        if value is None:
            continue
        day = datetime.fromtimestamp(int(stamp), UTC).date().isoformat()
        rows[day] = float(value)
    return rows


def _parse_treasury(text: str) -> dict[str, dict[str, float]]:
    parsed = {"yield_2y": {}, "yield_10y": {}, "yield_30y": {}}
    columns = {"yield_2y": "2 Yr", "yield_10y": "10 Yr", "yield_30y": "30 Yr"}
    for row in csv.DictReader(io.StringIO(text)):
        raw = (row.get("Date") or "").strip()
        parts = raw.split("/")
        if len(parts) != 3:
            continue
        month, day, year = parts
        iso = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        for name, column in columns.items():
            value = (row.get(column) or "").strip()
            if value in {"", "N/A"}:
                continue
            try:
                parsed[name][iso] = float(value)
            except ValueError:
                continue
    return parsed


def _yahoo_symbols(config: Config) -> dict[str, str]:
    symbols = {
        "spy": "SPY", "qqq": "QQQ", "tlt": "TLT", "hyg": "HYG", "lqd": "LQD",
        "gold": "GC=F", "gld": "GLD", "dxy": "DX-Y.NYB", "wti_fut": "CL=F",
        "brent_fut": "BZ=F", "vix_yahoo": "^VIX", "btc": "BTC-USD",
    }
    for name in (*config.portfolio.universe, *config.phillip.names):
        symbols[name] = name
    return symbols


def _prefer(primary: dict[str, float], fallback: dict[str, float], minimum: int = 200) -> dict[str, float]:
    return primary if len(primary) >= minimum else fallback


def fetch_panel(config: Config, cache_dir: Path, *, end: date | None = None) -> SeriesPanel:
    """Download, cache, and normalize. Re-runs reuse files already in cache_dir."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    start = config.window.warmup_start
    stop = end or (config.window.end + timedelta(days=7))
    # A daily bar dated today is not a close until after the US cash session.
    now = datetime.now(UTC)
    if now.hour < 21 and stop >= now.date():
        stop = now.date() - timedelta(days=1)
    sources: dict[str, str] = {}
    series: dict[str, dict[str, float]] = {}
    headers = {"User-Agent": "Mozilla/5.0 rocket-research"}

    def _log(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    with httpx.Client(timeout=60, headers=headers, follow_redirects=True) as client:
        _log("treasury yields")
        yields = {"yield_2y": {}, "yield_10y": {}, "yield_30y": {}}
        for year in range(start.year, stop.year + 1):
            path = cache_dir / f"treasury_{year}.csv"
            try:
                raw = _cached(path, lambda year=year: _get(client, TREASURY_URL.format(year=year)).content)
                parsed = _parse_treasury(raw.decode("utf-8", "replace"))
                for name, points in parsed.items():
                    yields[name].update(points)
            except (httpx.HTTPError, OSError, UnicodeError) as exc:
                sources[f"treasury_{year}"] = f"failed:{type(exc).__name__}"
        for name, points in yields.items():
            series[name] = {day: value for day, value in points.items() if start.isoformat() <= day <= stop.isoformat()}
            sources[name] = "US Treasury daily par yield curve"

        _log("fed funds")
        effr_path = cache_dir / "effr.json"
        try:
            raw = _cached(
                effr_path,
                lambda: _get(client, EFFR_URL, params={"startDate": start.isoformat(), "endDate": stop.isoformat()}).content,
            )
            payload = orjson.loads(raw)
            series["fed_funds"] = {
                row["effectiveDate"]: float(row["percentRate"])
                for row in payload.get("refRates") or []
                if row.get("effectiveDate") and row.get("percentRate") is not None
            }
            sources["fed_funds"] = "New York Fed EFFR"
        except (httpx.HTTPError, OSError, orjson.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            sources["fed_funds"] = f"failed:{type(exc).__name__}"

        _log("fred")
        for name, series_id in FRED_SERIES.items():
            points: dict[str, float] = {}
            for chunk_start, chunk_end in _quarters(start, stop):
                path = cache_dir / f"fred_{series_id}_{chunk_start.isoformat()}.csv"
                try:
                    raw = _cached(
                        path,
                        lambda series_id=series_id, chunk_start=chunk_start, chunk_end=chunk_end: _get(
                            client, FRED_URL,
                            params={"id": series_id, "cosd": chunk_start.isoformat(), "coed": chunk_end.isoformat()},
                        ).content,
                    )
                    points.update(_parse_fred(raw.decode("utf-8", "replace")))
                except (httpx.HTTPError, OSError, UnicodeError) as exc:
                    sources[name] = f"partial:{type(exc).__name__}"
            if points:
                series[name] = points
                sources.setdefault(name, f"FRED {series_id}")

        period1 = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp())
        period2 = int(datetime(stop.year, stop.month, stop.day, tzinfo=UTC).timestamp())
        _log("yahoo")
        for name, symbol in _yahoo_symbols(config).items():
            path = cache_dir / f"yahoo_{quote(symbol, safe='')}.json"
            try:
                raw = _cached(
                    path,
                    lambda symbol=symbol: _get(
                        client, YAHOO.format(symbol=quote(symbol, safe="")),
                        params={"period1": period1, "period2": period2, "interval": "1d", "events": "div,splits"},
                    ).content,
                )
                points = _parse_yahoo(orjson.loads(raw))
                if points:
                    series[name] = points
                    sources[name] = f"Yahoo Finance {symbol} adjusted close"
            except (httpx.HTTPError, OSError, orjson.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                sources[name] = f"failed:{type(exc).__name__}"

        _log("deribit dvol")
        dvol: dict[str, float] = {}
        year = start.year
        while year <= stop.year:
            path = cache_dir / f"dvol_{year}.json"
            begin = datetime(year, 1, 1, tzinfo=UTC)
            finish = datetime(year + 1, 1, 1, tzinfo=UTC)
            try:
                raw = _cached(
                    path,
                    lambda begin=begin, finish=finish: _get(
                        client, f"{DERIBIT}/get_volatility_index_data",
                        params={
                            "currency": "BTC",
                            "start_timestamp": int(begin.timestamp() * 1000),
                            "end_timestamp": int(finish.timestamp() * 1000),
                            "resolution": "86400",
                        },
                    ).content,
                )
                for row in (orjson.loads(raw).get("result") or {}).get("data") or []:
                    if len(row) < 5:
                        continue
                    day = datetime.fromtimestamp(int(row[0]) / 1000, UTC).date().isoformat()
                    dvol[day] = float(row[4])
            except (httpx.HTTPError, OSError, orjson.JSONDecodeError, TypeError, ValueError) as exc:
                sources["dvol"] = f"failed:{type(exc).__name__}"
            year += 1
        if dvol:
            series["dvol"] = dvol
            sources["dvol"] = "Deribit BTC DVOL daily close"

        _log("deribit funding")
        funding: dict[str, float] = defaultdict(float)
        cursor = date(start.year, start.month, 1)
        while cursor <= stop:
            nxt = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            path = cache_dir / f"funding_{cursor.isoformat()}.json"
            begin = datetime(cursor.year, cursor.month, cursor.day, tzinfo=UTC)
            finish = datetime(nxt.year, nxt.month, nxt.day, tzinfo=UTC)
            try:
                raw = _cached(
                    path,
                    lambda begin=begin, finish=finish: _get(
                        client, f"{DERIBIT}/get_funding_rate_history",
                        params={
                            "instrument_name": "BTC-PERPETUAL",
                            "start_timestamp": int(begin.timestamp() * 1000),
                            "end_timestamp": int(finish.timestamp() * 1000),
                        },
                    ).content,
                )
                for row in orjson.loads(raw).get("result") or []:
                    day = datetime.fromtimestamp(int(row["timestamp"]) / 1000, UTC).date().isoformat()
                    funding[day] += float(row["interest_1h"])
            except (httpx.HTTPError, OSError, orjson.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                sources["funding_daily"] = f"failed:{type(exc).__name__}"
            cursor = nxt
        if funding:
            series["funding_daily"] = dict(funding)
            sources["funding_daily"] = "Deribit BTC-PERPETUAL sum of hourly interest_1h"

    series["wti"] = _prefer(series.get("wti_fred", {}), series.get("wti_fut", {}))
    series["brent"] = _prefer(series.get("brent_fred", {}), series.get("brent_fut", {}))
    series["vix"] = _prefer(series.get("vix_fred", {}), series.get("vix_yahoo", {}))
    series["dollar"] = _prefer(series.get("dxy", {}), series.get("dollar_broad", {}))
    series["gold"] = _prefer(series.get("gold", {}), series.get("gld", {}), minimum=200)
    sources["wti"] = sources.get("wti_fred", sources.get("wti_fut", "missing"))
    if len(series.get("wti_fred", {})) < 200:
        sources["wti"] = sources.get("wti_fut", sources["wti"])
    if len(series.get("brent_fred", {})) < 200:
        sources["brent"] = sources.get("brent_fut", sources.get("brent", "missing"))
    else:
        sources["brent"] = sources.get("brent_fred", "missing")
    if len(series.get("vix_fred", {})) < 200:
        sources["vix"] = sources.get("vix_yahoo", sources.get("vix", "missing"))
    else:
        sources["vix"] = sources.get("vix_fred", "missing")
    if len(series.get("dxy", {})) < 200:
        sources["dollar"] = sources.get("dollar_broad", "missing")
    else:
        sources["dollar"] = sources.get("dxy", "missing")
    keep = {
        "yield_2y", "yield_10y", "yield_30y", "fed_funds", "wti", "brent", "vix",
        "hy_oas", "ig_oas", "dollar", "gold", "tlt", "hyg", "lqd", "btc", "dvol",
        "funding_daily", "spy", "qqq", *config.portfolio.universe, *config.phillip.names,
    }
    start_iso, stop_iso = start.isoformat(), stop.isoformat()
    cleaned = {}
    for name, points in series.items():
        if name not in keep or not points:
            continue
        windowed = {day: value for day, value in points.items() if start_iso <= day <= stop_iso}
        if windowed:
            cleaned[name] = windowed
    return SeriesPanel(cleaned, {
        "sources": {name: sources.get(name, "") for name in sorted(cleaned)},
        "warmup_start": start.isoformat(),
        "built_through": stop.isoformat(),
    })
