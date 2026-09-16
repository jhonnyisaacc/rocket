"""Autonomous short snapshots from Yahoo history. Missing factors stay unknown."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from rocket.workflows.shorts import UNIVERSE


def _closes(symbol: str, http: httpx.Client) -> tuple[list[float], str | None]:
    for host in ("query2", "query1"):
        try:
            response = http.get(
                f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"range": "3mo", "interval": "1d"},
                headers={"User-Agent": "Mozilla/5.0"}, timeout=15,
            )
            response.raise_for_status()
            data = response.json()["chart"]["result"][0]
            if not data.get("indicators", {}).get("quote"):
                raise ValueError("missing quote history")
            break
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            if host == "query1":
                raise
    result = response.json()["chart"]["result"][0]
    closes = [float(value) for value in result["indicators"]["quote"][0]["close"] if value is not None]
    stamp = datetime.fromtimestamp(result["meta"]["regularMarketTime"], UTC).isoformat()
    return closes, stamp


def acquire_short_snapshot(
    *,
    now: datetime | None = None,
    universe=None,
    http: httpx.Client | None = None,
    fundamentals: Callable[[str], Mapping[str, Any]] | None = None,
) -> list[dict]:
    fixed_now = now
    now = now or datetime.now(UTC)
    universe = UNIVERSE if universe is None else universe
    symbols = sorted(set(universe) | {v for v in universe.values() if v} | {"SPY"})
    owns = http is None
    client = http or httpx.Client(timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    histories: dict[str, tuple[list[float] | None, str, str | None, bool]] = {}
    try:
        for symbol in symbols:
            try:
                series, observed = _closes(symbol, client)
                stamp = datetime.fromisoformat(observed) if observed else None
                valid = (
                    stamp is not None
                    and stamp.tzinfo is not None
                    and timedelta(0) <= (fixed_now or datetime.now(UTC)) - stamp <= timedelta(days=5)
                    and len(series) >= 21
                    and all(math.isfinite(value) and value > 0 for value in series[-21:])
                )
                histories[symbol] = (series, "Yahoo Finance chart API", observed, valid)
            except Exception:
                histories[symbol] = (None, "unavailable", None, False)
    finally:
        if owns:
            client.close()
    spy = histories["SPY"]
    rows = []
    for ticker, sector in universe.items():
        series, source, observed, valid = histories[ticker]
        sec = histories.get(sector, (None, "unknown sector", None, False))
        row = {
            "ticker": ticker,
            "source": source,
            "event_time": observed,
            "available_at": now.isoformat() if valid else None,
            "acquisition_mode": "LIVE",
            "required_factors": ["company_fundamentals", "technical_breakdown"],
            "provider_health": "HEALTHY" if valid else "DATA_UNAVAILABLE",
            "company_fundamentals": None,
            "catalyst": None,
            "earnings_revision_deterioration": None,
            "positioning_crowding": None,
            "valuation_support": None,
        }
        if valid and series:
            prior = series[-21:-1]
            row["technical_breakdown"] = series[-1] < min(prior)
            row["current_price"] = series[-1]
            row["technical_setup"] = {"rule": "close below prior 20-session low", "prior_low": min(prior)}
            row["entry"] = {"concept": "retest of broken 20-session support", "level": min(prior)}
            row["invalidation"] = max(prior)
            if len(series) >= 21:
                row["stock_20d_return"] = series[-1] / series[-21] - 1
            if len(series) >= 61:
                row["stock_60d_return"] = series[-1] / series[-61] - 1
        row["provider_attempts"] = [{"name": f"yahoo.history:{symbol}",
                                     "status": "HEALTHY" if histories[symbol][3] else "UNAVAILABLE",
                                     "coverage": str(len(histories[symbol][0] or []))}
                                    for symbol in dict.fromkeys((ticker, sector, "SPY")) if symbol]
        if fundamentals is not None:
            try:
                extra = fundamentals(ticker)
            except Exception as exc:
                extra = {"provider_attempts": [{"name": f"fundamentals:{ticker}", "status": "UNAVAILABLE",
                                                "failure_kind": type(exc).__name__}]}
            row["provider_attempts"].extend(extra.get("provider_attempts", []))
            if isinstance(extra, Mapping):
                for key in (
                    "company_fundamentals",
                    "earnings_revision_deterioration",
                    "valuation_support",
                    "pe_ttm",
                    "eps_growth",
                    "fundamentals_source",
                    "eps_growth_basis",
                    "cash_flow_quality",
                    "eps_revision_30d",
                    "revenue_revision_30d",
                    "catalysts",
                ):
                    if key in extra:
                        row[key] = extra[key]
        if spy[3] and spy[0]:
            bench = spy[0]
            row["macro_regime"] = "risk_off" if bench[-1] < sum(bench[-20:]) / 20 else "neutral"
            row["spy_20d_return"] = bench[-1] / bench[-21] - 1 if len(bench) >= 21 else None
        if sec[3] and sec[0] and len(sec[0]) >= 21:
            row["sector_20d_return"] = sec[0][-1] / sec[0][-21] - 1
        if sec[3] and spy[3] and sec[0] and spy[0]:
            sector_return = sec[0][-1] / sec[0][-21] - 1
            bench_return = spy[0][-1] / spy[0][-21] - 1
            row["sector_weakness"] = sector_return < 0 and sector_return < bench_return
        if valid and series:
            from rocket.providers.short_quality import (
                classify_regime,
                failed_retest,
                history_target,
                relative_strength,
                risk_reward,
            )
            relative = relative_strength(series, sec[0] if sec[3] else None, spy[0] if spy[3] else None)
            row["relative_vs_sector"] = relative["relative_vs_sector"]
            row["relative_vs_market"] = relative["relative_vs_market"]
            retest = failed_retest(series)
            row["failed_retest"] = retest["failed_retest"]
            row["regime"] = classify_regime(spy[0] if spy[3] else None, sec[0] if sec[3] else None)["regime"]
            row["target"] = history_target(series)
            row["risk_reward"] = risk_reward(series[-1], row.get("invalidation"), row.get("target"))
        if fundamentals is None:
            row["provider_attempts"].append({"name": f"fundamentals:{ticker}", "status": "UNAVAILABLE", "failure_kind": "NotConfigured"})
        row["provider_health"] = "HEALTHY" if all(p["status"] == "HEALTHY" for p in row["provider_attempts"]) else "PARTIAL" if valid else "UNAVAILABLE"
        rows.append(row)
    acquired = fixed_now or datetime.now(UTC)
    for row in rows:
        if row["available_at"] is not None:
            row["available_at"] = acquired.isoformat()
    return rows


def live_fundamentals_fetcher() -> Callable[[str], Mapping[str, Any]] | None:
    from rocket.providers.fundamentals import fundamentals_row

    return fundamentals_row


def _optional_call(fetcher, ticker, *, now):
    if fetcher is None:
        return None
    try:
        return fetcher(ticker, now=now)
    except TypeError:
        return fetcher(ticker)


def acquire_short_snapshot_v2(
    *,
    now: datetime | None = None,
    universe=None,
    http: httpx.Client | None = None,
    store=None,
    fundamentals: Callable[[str], Mapping[str, Any]] | None = None,
    market_fetcher: Callable[..., list[dict]] | None = None,
    sec_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    catalyst_fetcher: Callable[..., list] | None = None,
    estimates_fetcher: Callable[..., list] | None = None,
    tokenized_fetcher: Callable[..., Sequence[Mapping[str, Any]]] | None = None,
) -> list[dict]:
    """Live Shorts v2 acquisition. Missing optional providers stay UNKNOWN."""
    from rocket.providers.estimate_revisions import live_revisions
    from rocket.providers.short_events import bearish_catalysts
    from rocket.providers.tokenized_equities import acquire_tokenized_snapshot, eligibility

    decided = now or datetime.now(UTC)
    market = market_fetcher or acquire_short_snapshot
    rows = market(universe=universe, now=now, http=http, fundamentals=fundamentals)
    token_rows: Sequence[Mapping[str, Any]] = ()
    token_attempts = []
    try:
        if tokenized_fetcher is not None:
            token_rows = tokenized_fetcher()
            token_attempts.append({"name": "tokenized_equities", "status": "HEALTHY", "coverage": str(len(token_rows))})
        else:
            snapshot = acquire_tokenized_snapshot(http=http, now=decided)
            token_rows = snapshot.records
            token_attempts.extend(list(snapshot.extras.get("provider_attempts") or []) or [{"name": "tokenized_equities", "status": snapshot.status.value}])
    except Exception as exc:
        token_attempts.append({"name": "tokenized_equities", "status": "UNAVAILABLE", "failure_kind": type(exc).__name__})

    def default_sec(ticker: str, *, now: datetime) -> Mapping[str, Any]:
        from rocket.providers.sec_facts import SecFacts
        result = SecFacts(http=http).fundamentals(ticker, now=now)
        row = dict(result.records[0]) if result.records else {}
        row["provider_attempts"] = [{"name": "sec.companyfacts", "status": result.status.value, "failure_kind": result.failure_kind}]
        return row

    def default_catalysts(ticker: str, *, now: datetime) -> list:
        from rocket.providers.sec_facts import SecFacts
        result = SecFacts(http=http).catalysts(ticker, now=now)
        return list(result.records)

    def default_estimates(ticker: str, *, now: datetime) -> list:
        del now
        from rocket.providers.fmp import FMPClient
        result = FMPClient().analyst_estimates(ticker)
        return list(result.records)

    for row in rows:
        ticker = row["ticker"]
        row.setdefault("provider_attempts", [])
        row["provider_attempts"].extend(token_attempts)
        try:
            sec_row = _optional_call(sec_fetcher or default_sec, ticker, now=decided) or {}
        except Exception as exc:
            sec_row = {"provider_attempts": [{"name": "sec.companyfacts", "status": "UNAVAILABLE", "failure_kind": type(exc).__name__}]}
        if isinstance(sec_row, Mapping):
            row["provider_attempts"].extend(sec_row.get("provider_attempts") or [])
            if sec_row.get("cash_flow_quality") is not None:
                row["cash_flow_quality"] = sec_row["cash_flow_quality"]
            if sec_row.get("company_fundamentals") is not None:
                row["company_fundamentals"] = sec_row["company_fundamentals"]
                for key in ("eps_growth", "eps_growth_basis", "fundamentals_source"):
                    if sec_row.get(key) is not None:
                        row[key] = sec_row[key]
        try:
            cats = _optional_call(catalyst_fetcher or default_catalysts, ticker, now=decided) or []
        except Exception:
            cats = []
        row["catalysts"] = list(cats) if isinstance(cats, list) else []
        bearish = bearish_catalysts(row["catalysts"], now=decided)
        row["catalyst"] = bearish[0] if bearish else None
        try:
            estimates = _optional_call(estimates_fetcher or default_estimates, ticker, now=decided) or []
        except Exception:
            estimates = []
        revisions = live_revisions(ticker, estimates if isinstance(estimates, list) else [], store=store, now=decided)
        row["eps_revision_30d"] = revisions.get("eps_revision_30d")
        row["revenue_revision_30d"] = revisions.get("revenue_revision_30d")
        row["eps_revision_change"] = revisions.get("eps_revision_change")
        row["revenue_revision_change"] = revisions.get("revenue_revision_change")
        row["revision_reason"] = revisions.get("revision_reason")
        row["snapshots_persisted"] = revisions.get("snapshots_persisted")
        row["provider_attempts"].append({
            "name": "estimate_snapshots",
            "status": "HEALTHY" if revisions.get("snapshots_persisted") else "PARTIAL",
            "coverage": str(revisions.get("snapshots_persisted") or 0),
        })
        elig = eligibility(ticker, token_rows, now=decided)
        row["research_eligibility"] = elig["research"]["status"]
        row["execution_eligibility"] = elig["execution"]["status"]
        row["tokenized"] = elig
        row["acquisition_path"] = "shorts_v2"
        row["provider_health"] = (
            "HEALTHY" if all(p.get("status") == "HEALTHY" for p in row["provider_attempts"])
            else "PARTIAL" if row.get("technical_breakdown") is not None
            else "UNAVAILABLE"
        )
    return rows
