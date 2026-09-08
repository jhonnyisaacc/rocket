"""Exact instrument catalog for Cava; no substitution across related measures."""

from datetime import UTC, datetime, timedelta

import httpx

from rocket.claims import shift_month
from rocket.providers.fred import _record_date, _record_value, fetch_series
from rocket.providers.http import get_read

FRED = {"CPI": "CPIAUCNS", "CORE_CPI": "CPILFENS", "CPI_YOY": "CPIAUCNS",
        "CORE_CPI_YOY": "CPILFENS", "US10Y": "DGS10", "WALCL": "WALCL",
        "TGA": "WDTGAL", "RRP": "RRPONTSYD"}
MARKET = {"DXY": "DX-Y.NYB", "BTC_USD": "BTC-USD", "SP500": "^GSPC",
          "NASDAQ_COMPOSITE": "^IXIC", "GOLD_FUTURES": "GC=F", "COPPER_FUTURES": "HG=F"}


def fetch_indicator(measure, *, http=None):
    if measure == "NET_LIQUIDITY":
        parts = {name: fetch_indicator(name, http=http) for name in ("WALCL", "TGA", "RRP")}
        values = {name: {r["date"]: r["value"] for r in part["records"]} for name, part in parts.items()}
        days = set.intersection(*(set(part) for part in values.values()))
        return {"measure": measure, "source": "FRED exact-date WALCL minus TGA minus RRP", "citation": "https://fred.stlouisfed.org/series/WALCL",
                "retrieved_at": max(part["retrieved_at"] for part in parts.values()), "unit": "billion USD", "max_age_days": 10,
                "components": parts, "formula": "WALCL / 1000 - WDTGAL / 1000 - RRPONTSYD; identical observation dates only",
                "records": [{"date": d, "value": values["WALCL"][d] / 1000 - values["TGA"][d] / 1000 - values["RRP"][d]} for d in sorted(days)]}
    if measure == "GOLD_SPOT":
        from rocket.config import env
        key = env("MASSIVE_API_KEY")
        if not key:
            raise ValueError("exact gold spot provider not configured")
        now = datetime.now(UTC)
        url = f"https://api.massive.com/v2/aggs/ticker/C:XAUUSD/range/1/day/{(now-timedelta(days=730)).date()}/{now.date()}"
        owns = http is None
        client = http or httpx.Client(timeout=20)
        try:
            response = get_read(client, url, params={"limit": 5000, "sort": "asc"}, headers={"Authorization": f"Bearer {key}"})
            response.raise_for_status()
            raw = response.json()
            if raw.get("ticker") != "C:XAUUSD" or raw.get("next_url"):
                raise ValueError("exact gold instrument or coverage mismatch")
            return {"measure": measure, "source": "Massive forex aggregates", "citation": url,
                    "retrieved_at": datetime.now(UTC).isoformat(), "unit": "USD per troy ounce", "max_age_days": 5,
                    "records": [{"date": datetime.fromtimestamp(row["t"] / 1000, UTC).date().isoformat(), "value": row["c"]} for row in raw.get("results", [])]}
        finally:
            if owns:
                client.close()
    if measure in FRED:
        symbol = FRED[measure]
        raw, source = fetch_series(symbol)
        values = {}
        for row in raw.get("records", []):
            day, value = _record_date(row), _record_value(row, symbol)
            if day and value is not None:
                values[str(day)[:10]] = value
        if measure.endswith("YOY"):
            from datetime import date
            values = {day: (value / values[prior] - 1) * 100 for day, value in values.items()
                      if (prior := shift_month(date.fromisoformat(day), -12).isoformat()) in values and values[prior] != 0}
        return {"measure": measure, "records": [{"date": d, "value": v} for d, v in sorted(values.items())],
                "source": source, "citation": f"https://fred.stlouisfed.org/series/{symbol}",
                "retrieved_at": raw.get("retrieved_at"), "max_age_days": 90 if "CPI" in measure else 10 if measure in {"TGA", "WALCL"} else 5,
                "unit": "percent" if "YOY" in measure or measure == "US10Y" else "index" if "CPI" in measure else "billion USD" if measure == "RRP" else "million USD"}
    if measure not in MARKET:
        raise ValueError("exact instrument acquisition not supported")
    symbol = MARKET[measure]
    owns = http is None
    client = http or httpx.Client(timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    try:
        for host in ("query2", "query1"):
            try:
                url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}"
                response = get_read(client, url, params={"range": "2y", "interval": "1d"})
                raw = response.json()["chart"]["result"][0]
                if raw["meta"]["symbol"] != symbol:
                    raise ValueError("market instrument mismatch")
                records = [{"date": datetime.fromtimestamp(t, UTC).date().isoformat(), "value": float(v)}
                           for t, v in zip(raw["timestamp"], raw["indicators"]["quote"][0]["close"], strict=True) if v is not None]
                return {"measure": measure, "records": records, "source": "Yahoo Finance chart API",
                        "citation": url, "retrieved_at": datetime.now(UTC).isoformat(), "max_age_days": 5,
                        "unit": raw["meta"].get("currency", "index"), "instrument": symbol}
            except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError):
                if host == "query1":
                    raise
    finally:
        if owns:
            client.close()
