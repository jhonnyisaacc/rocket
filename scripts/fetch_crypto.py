"""Fetch free BTC research data. No keys, public endpoints only.

Sources (documented in docs/crypto/EXPERIMENTS.md):
- Binance spot klines (daily) 2019-01-01 to present.
- Perp funding history: Binance fapi (8h), Bybit v5 (8h).
- Deribit DVOL daily (get_volatility_index_data; gaps left as gaps).

Writes data/crypto/*.json. Idempotent: skips refetch when the file already
covers the requested range unless --refresh is passed.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "crypto"

BINANCE = "https://api.binance.com/api/v3/klines"
FAPI = "https://fapi.binance.com/fapi/v1/fundingRate"
BYBIT = "https://api.bybit.com/v5/market/funding/history"
DERIBIT_VOL = "https://www.deribit.com/api/v2/public/get_volatility_index_data"


def get(url: str, retries: int = 5) -> object:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:  # rate limits, wobbles; back off
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET failed: {url}: {last}")


def fetch_klines_daily(symbol: str, start_ms: int, end_ms: int) -> list[list]:
    out: list[list] = []
    cursor = start_ms
    while True:
        url = (
            f"{BINANCE}?symbol={symbol}&interval=1d&limit=1000&startTime={cursor}&endTime={end_ms}"
        )
        batch = get(url)
        assert isinstance(batch, list)
        if not batch:
            break
        out.extend(batch)
        cursor = int(batch[-1][0]) + 86_400_000
        if len(batch) < 1000 or cursor >= end_ms:
            break
        time.sleep(0.3)
    return out


def fetch_funding_binance(start_ms: int, end_ms: int) -> list[dict]:
    out: list[dict] = []
    cursor = start_ms
    while True:
        url = f"{FAPI}?symbol=BTCUSDT&limit=1000&startTime={cursor}&endTime={end_ms}"
        batch = get(url)
        assert isinstance(batch, list)
        if not batch:
            break
        out.extend(batch)
        cursor = int(batch[-1]["fundingTime"]) + 1
        if len(batch) < 1000 or cursor >= end_ms:
            break
        time.sleep(0.3)
    return out


def fetch_funding_bybit(start_ms: int, end_ms: int) -> list[dict]:
    # Bybit ignores start/end and always returns the newest prints (cap 200,
    # ~25 days). Recent-only cross-check against Binance, not history.
    url = f"{BYBIT}?category=linear&symbol=BTCUSDT&limit=200"
    payload = get(url)
    assert isinstance(payload, dict)
    return ((payload.get("result") or {}).get("list")) or []


def fetch_dvol(start_ms: int, end_ms: int) -> list[dict]:
    # DVOL starts 2021-04; fetch year-long chunks and always advance, so an
    # empty early window cannot stall the walk.
    out: list[dict] = []
    year_ms = 366 * 86_400_000
    cursor = max(start_ms, 1617235200000)
    seen: set[int] = set()
    while cursor < end_ms:
        chunk_end = min(cursor + year_ms, end_ms)
        url = (
            f"{DERIBIT_VOL}?currency=BTC&start_timestamp={cursor}"
            f"&end_timestamp={chunk_end}&resolution=1D"
        )
        payload = get(url)
        assert isinstance(payload, dict)
        batch = ((payload.get("result") or {}).get("data")) or []
        for row in batch:
            if row[0] not in seen:
                seen.add(row[0])
                out.append(row)
        if not batch:
            time.sleep(0.3)
        cursor = chunk_end + 1
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)

    start_ms = 1546300800000  # 2019-01-01T00:00:00Z
    end_ms = 1790870400000  # 2026-10-01T00:00:00Z (fetch to present)

    btc_path = DATA / "btc_daily.json"
    if args.refresh or not btc_path.exists():
        klines = fetch_klines_daily("BTCUSDT", start_ms, end_ms)
        rows = [
            {
                "t": int(k[0]),
                "o": float(k[1]),
                "h": float(k[2]),
                "l": float(k[3]),
                "c": float(k[4]),
                "v": float(k[5]),
            }
            for k in klines
        ]
        btc_path.write_text(json.dumps({"source": "Binance BTCUSDT 1d", "rows": rows}))
        print(f"btc_daily: {len(rows)} rows")
    else:
        print("btc_daily: cached")

    fund_path = DATA / "funding_binance.json"
    if args.refresh or not fund_path.exists():
        rows = fetch_funding_binance(start_ms, end_ms)
        fund_path.write_text(json.dumps({"source": "Binance BTCUSDT 8h", "rows": rows}))
        print(f"funding_binance: {len(rows)} rows")
    else:
        print("funding_binance: cached")

    bybit_path = DATA / "funding_bybit.json"
    if args.refresh or not bybit_path.exists():
        rows = fetch_funding_bybit(start_ms, end_ms)
        bybit_path.write_text(json.dumps({"source": "Bybit BTCUSDT 8h", "rows": rows}))
        print(f"funding_bybit: {len(rows)} rows")
    else:
        print("funding_bybit: cached")

    dvol_path = DATA / "dvol.json"
    if args.refresh or not dvol_path.exists():
        rows = fetch_dvol(start_ms, end_ms)
        dvol_path.write_text(json.dumps({"source": "Deribit DVOL 1D", "rows": rows}))
        print(f"dvol: {len(rows)} rows")
    else:
        print("dvol: cached")


if __name__ == "__main__":
    main()
