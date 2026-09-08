"""Structured news feeds. Reporting is context, never automatic factual verification."""

from datetime import UTC, datetime, timedelta

from rocket.models import OperationalStatus
from rocket.providers.dispatch import acquire
from rocket.providers.fmp import FMPClient
from rocket.providers.protocols import ProviderResult


def acquire_news(symbol=None, *, fmp=None, openbb_fetcher=None):
    fmp = fmp or FMPClient()
    def primary():
        if not fmp.configured():
            return ProviderResult(OperationalStatus.UNAVAILABLE, source="fmp.news", failure_kind="NotConfigured")
        rows = fmp._get("/news/stock" if symbol else "/news/general-latest",
                        params={"symbols": symbol, "limit": 20} if symbol else {"limit": 20})
        if not isinstance(rows, list):
            raise ValueError("invalid news schema")
        return normalize(rows, "fmp.news")
    def fallback():
        fetch = openbb_fetcher
        if fetch is None:
            from rocket.providers.openbb_bridge import read_openbb
            fetch = lambda **params: read_openbb("news.company" if symbol else "news.world", **params)
        data = fetch(symbol=symbol, provider="yfinance", limit=20) if symbol else fetch(provider="fmp", limit=20)
        rows = data.results if hasattr(data, "results") else data
        return normalize([r.model_dump() if hasattr(r, "model_dump") else r for r in rows], "OpenBB.news")
    return acquire("news", [("fmp.news", primary), ("openbb.news", fallback)], required=False,
                   sufficient=lambda r: r.status is OperationalStatus.HEALTHY)


def normalize(rows, source):
    records = []
    for row in rows:
        title = row.get("title")
        url = row.get("url")
        published = row.get("publishedDate") or row.get("date")
        if not title or not url or not published:
            continue
        try:
            stamp = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=UTC)
            if not timedelta(0) <= datetime.now(UTC) - stamp <= timedelta(days=7):
                continue
        except ValueError:
            continue
        records.append({"title": title, "url": url, "published_at": str(published),
                        "publisher": row.get("publisher") or row.get("site"), "symbol": row.get("symbol"),
                        "source": source, "kind": "REPORTED_CONTEXT", "verified_fact": False})
    return ProviderResult(OperationalStatus.HEALTHY if records or not rows else OperationalStatus.PARTIAL,
                          tuple(records), datetime.now(UTC), source=source)


def company_news_context(symbol):
    import re
    result = acquire_news(symbol)
    rows = list(result.result.records) if result.result else []
    material = [r for r in rows if re.search(r"\b(bankruptcy|restatement|fraud|acquisition|merger|guidance|recall|investigation)\b", r["title"], re.IGNORECASE)]
    return {"news": rows, "material_news_ids": sorted(r["url"] for r in material),
            "meaningful_new_information": bool(material),
            "news_interpretation": "Reporting merits review; headline matching establishes neither truth nor thesis invalidation.",
            "news_provider_attempts": [a.to_dict() for a in result.attempts]}
