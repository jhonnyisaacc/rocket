"""Historical listed-security prices with split/dividend-adjusted comparison."""

from datetime import UTC, datetime

import httpx

from rocket.providers.http import get_read


def price_history(ticker, *, http=None):
    owns = http is None
    client = http or httpx.Client(timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
    try:
        response = get_read(client, url, params={"range": "5y", "interval": "1d", "events": "splits,div"})
        response.raise_for_status()
        data = response.json()["chart"]["result"][0]
        if data["meta"]["symbol"] != ticker:
            raise ValueError("historical asset identity mismatch")
        closes = data["indicators"]["quote"][0]["close"]
        adjusted = data["indicators"].get("adjclose", [{}])[0].get("adjclose", [None] * len(closes))
        return {"source": "Yahoo Finance chart API", "citation": url,
                "retrieved_at": datetime.now(UTC).isoformat(), "currency": data["meta"].get("currency"),
                "records": [{"date": datetime.fromtimestamp(t, UTC).date().isoformat(), "close": close, "adjusted_close": adj}
                            for t, close, adj in zip(data["timestamp"], closes, adjusted, strict=True)]}
    finally:
        if owns:
            client.close()


def transaction_context(history, transaction_date, *, now):
    import math

    from rocket.clock import equity_observation_fresh
    from rocket.pit import parse_datetime
    rows = history.get("records", [])
    available = parse_datetime(history.get("retrieved_at"))
    if not history.get("source") or not history.get("citation") or not available or available > now:
        return {}
    then = next((r for r in rows if r["date"] == transaction_date), None)
    current = max(rows, key=lambda r: r["date"]) if rows else None
    if not then or not current or not equity_observation_fresh(current["date"] + "T00:00:00+00:00", now, daily=True):
        return {}
    if not all(isinstance(r.get(k), (int, float)) and not isinstance(r[k], bool) and math.isfinite(r[k]) and r[k] > 0 for r in (then, current) for k in ("close", "adjusted_close")):
        return {}
    return {"historical_price": then["close"], "historical_price_status": "SUPPORTED",
            "historical_price_source": history["citation"], "historical_price_date": then["date"],
            "historical_availability": None, "history_retrieved_at": history["retrieved_at"],
            "move_since_transaction": current["adjusted_close"] / then["adjusted_close"] - 1,
            "move_basis": "adjusted close comparison, including corporate actions; not politician execution price"}
