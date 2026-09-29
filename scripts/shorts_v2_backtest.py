#!/usr/bin/env python3
"""Point-in-time Shorts v2 backtest. Research only; never uses current snapshots as history."""

from __future__ import annotations

import json
import math
import statistics
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from rocket.config import DEFAULT_CONFIG_DIR
from rocket.pit import parse_datetime
from rocket.providers.historical_prices import bars_eligible_at, daily_bars
from rocket.providers.ism_universe import (
    build_short_universe,
    primary_seed,
    select_contracting_industries,
    theme_attribution,
)
from rocket.providers.sec_facts import (
    SecFacts,
    compact_companyfacts,
    filings_from_submissions,
    reported_fundamentals,
    statement_pair_from_compact,
)
from rocket.providers.short_quality import (
    breakdown,
    classify_regime,
    failed_retest,
    forward_excursions,
    history_target,
    prior_session_high,
    relative_strength,
    risk_reward,
)
from rocket.providers.tokenized_equities import acquire_tokenized_snapshot, eligibility
from rocket.workflows.shorts import classify_shorts_v2_edge, score_ism_short_candidate, score_shorts_v2

ROOT = Path(__file__).resolve().parents[1]
REPORTS_PATH = ROOT / "docs/analysis/data/ism_reports_2026.json"
OUT_JSON = ROOT / "docs/analysis/data/shorts_v2_backtest.json"
CACHE = ROOT / ".cache/shorts_v2"
SPARSE_TICKERS = {"CAT", "NUE", "DOW", "WY", "TXN", "VLO", "F", "PEP", "WMT", "UPS", "JPM", "GOOGL"}
HORIZONS = (5, 10, 20)
END = datetime(2026, 9, 16, 20, tzinfo=UTC)


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def load_reports():
    return json.loads(REPORTS_PATH.read_text())["reports"]


def load_exposures():
    return json.loads((DEFAULT_CONFIG_DIR / "industry_exposure.json").read_text())


def report_pairs(reports):
    by_month = {}
    for kind in ("manufacturing", "services"):
        for row in reports[kind]:
            by_month.setdefault(row["reference_month"], {})[kind] = row
    pairs = []
    for month in sorted(by_month):
        block = by_month[month]
        if "manufacturing" not in block or "services" not in block:
            continue
        available = max(parse_datetime(block["manufacturing"]["publication_at"]),
                        parse_datetime(block["services"]["publication_at"]))
        pairs.append({"reference_month": month, "available_at": available, **block})
    for index, pair in enumerate(pairs):
        pair["next_available"] = pairs[index + 1]["available_at"] if index + 1 < len(pairs) else END
    return pairs


def universe_for(pair, exposures, *, top_n=None, mapping_mode="fixed", sparse=False):
    selected = {}
    for kind in ("manufacturing", "services"):
        industries = pair[kind]["contracting"]
        selected[kind] = industries if top_n is None else select_contracting_industries(industries, limit=top_n)
    if sparse:
        filtered = {}
        for industry, rows in exposures.items():
            filtered[industry] = [row for row in rows if row["ticker"] in SPARSE_TICKERS]
        exposures = filtered
    return build_short_universe(
        selected,
        exposures,
        now=pair["available_at"],
        mapping_mode=mapping_mode,
        reference_month={kind: pair[kind]["reference_month"] for kind in ("manufacturing", "services")},
    )


def cache_json(path: Path, fetcher):
    if path.exists():
        return json.loads(path.read_text())
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = fetcher()
    path.write_text(json.dumps(payload) + "\n")
    return payload


def fetch_price(ticker, client):
    path = CACHE / "prices" / f"{ticker}.json"

    def load():
        try:
            return daily_bars(ticker, http=client, range="2y")
        except Exception as exc:
            return {"source": "unavailable", "error": type(exc).__name__, "records": []}

    if path.exists():
        payload = json.loads(path.read_text())
        records = payload.get("records") or []
        if records and "open" in records[0]:
            return payload
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = load()
    path.write_text(json.dumps(payload) + "\n")
    return payload


def load_sec_bundle(tickers, client):
    facts = SecFacts(http=client)
    try:
        facts._load_tickers(client)
    except Exception as exc:
        return {ticker: {"cik": None, "facts": None, "submissions": None, "error": type(exc).__name__} for ticker in tickers}
    bundles = {}
    for ticker in tickers:
        path = CACHE / "sec" / f"{ticker}.json"
        if path.exists():
            bundles[ticker] = json.loads(path.read_text())
            continue
        cik = facts.tickers.get(ticker)
        row = {"cik": cik, "facts": None, "submissions": None, "error": None}
        if not cik:
            row["error"] = "UnknownTicker"
        else:
            try:
                payload = client.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json").json()
                row["facts"] = compact_companyfacts(payload)
                time.sleep(0.15)
                submissions = client.get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
                row["submissions"] = submissions
                time.sleep(0.15)
            except Exception as exc:
                row["error"] = type(exc).__name__
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(row) + "\n")
        bundles[ticker] = row
    return bundles


def closes_as_of(history, now):
    return bars_eligible_at(history, now)


def series_from(bars, field="close"):
    return [row[field] for row in bars if row.get(field) is not None]


def fundamentals_as_of(bundle, now):
    if not bundle or not bundle.get("facts"):
        return {"company_fundamentals": None, "cash_flow_quality": {"state": "UNKNOWN"}, "historically_available": False}
    facts = bundle["facts"]
    if "facts" in facts and "us-gaap" in (facts.get("facts") or {}):
        latest, prior = statement_pair_from_compact(compact_companyfacts(facts), now=now)
    else:
        latest, prior = statement_pair_from_compact(facts, now=now)
    row = reported_fundamentals(latest, prior)
    row["historically_available"] = row.get("eps_growth") is not None or row.get("cash_flow_quality", {}).get("state") != "UNKNOWN"
    return row


def catalysts_as_of(bundle, now):
    if not bundle or not bundle.get("submissions"):
        return []
    return [row for row in filings_from_submissions(bundle["submissions"], now=now)
            if timedelta(0) <= now - parse_datetime(row["available_at"]) <= timedelta(days=45)]


def snapshot_row(seed, bars, sector_bars, spy_bars, fundamentals, catalysts, now, *, themes=None):
    closes = series_from(bars)
    opens = series_from(bars, "open")
    sector = series_from(sector_bars)
    spy = series_from(spy_bars)
    relative = relative_strength(closes, sector, spy)
    retest = failed_retest(closes)
    regime = classify_regime(spy, sector)
    price = closes[-1] if closes else None
    target = history_target(closes, opens=opens or None)
    stop = prior_session_high(closes)
    row = {
        "ticker": seed["ticker"],
        "asset": seed["ticker"],
        "candidate_sources": [{
            "direction": "short",
            "industry": theme.get("industry"),
            "rank": theme.get("ism_rank"),
            "report_type": theme.get("report_type"),
            "thesis": f"ISM {seed.get('reference_month')} {theme.get('report_type')}: {theme.get('industry')} contracting",
        } for theme in (themes or [{"industry": seed.get("industry"), "ism_rank": seed.get("ism_rank"), "report_type": seed.get("report_type")}])],
        "candidate_id": f"listed:{seed['ticker']}",
        "industry": seed.get("industry"),
        "ism_rank": seed.get("ism_rank"),
        "report_type": seed.get("report_type"),
        "themes": themes or [{"industry": seed.get("industry"), "ism_rank": seed.get("ism_rank"), "report_type": seed.get("report_type")}],
        "ism_contracting": True,
        "source": (bars[-1].get("source") if bars else None) or "Yahoo Finance chart API",
        "event_time": bars[-1]["event_time"] if bars else None,
        "available_at": bars[-1]["available_at"] if bars else None,
        "current_price": price,
        "technical_breakdown": breakdown(closes),
        "failed_retest": retest["failed_retest"],
        "relative_vs_sector": relative["relative_vs_sector"],
        "relative_vs_market": relative["relative_vs_market"],
        "stock_20d_return": relative["stock_return"],
        "sector_etf": seed.get("sector_etf"),
        "company_fundamentals": fundamentals.get("company_fundamentals"),
        "eps_growth": fundamentals.get("eps_growth"),
        "eps_growth_basis": fundamentals.get("eps_growth_basis"),
        "cash_flow_quality": fundamentals.get("cash_flow_quality"),
        "eps_revision_30d": "UNKNOWN",
        "revenue_revision_30d": "UNKNOWN",
        "revision_historically_available": False,
        "catalysts": catalysts,
        "regime": regime["regime"],
        "invalidation": stop,
        "target": target,
        "risk_reward": risk_reward(price, stop, target),
        "valuation_support": None,
    }
    return row


def entry_window(bars, future, *, mode):
    from rocket.providers.short_quality import research_entry_price
    if mode == "CLOSE_SIGNAL":
        row = research_entry_price(signal_close=(bars[-1] or {}).get("close"), next_open=None, mode=mode)
        return row["entry"], future, row["mode"]
    next_open = None if not future else future[0].get("open")
    row = research_entry_price(signal_close=None, next_open=next_open, mode="NEXT_SESSION_OPEN")
    return row["entry"], future, row["mode"]


def forward_stats(entry, window, horizons=HORIZONS):
    if entry is None:
        return {}
    out = {}
    for horizon in horizons:
        slice_ = (window or [])[:horizon]
        if len(slice_) < horizon:
            out[f"underlying_{horizon}d"] = None
            out[f"short_{horizon}d"] = None
            out[f"mae_{horizon}d"] = None
            out[f"mfe_{horizon}d"] = None
            continue
        highs = [row.get("high") if row.get("high") is not None else row.get("close") for row in slice_]
        lows = [row.get("low") if row.get("low") is not None else row.get("close") for row in slice_]
        closes = [row.get("close") for row in slice_]
        moves = forward_excursions(entry, highs, lows, closes)
        und = moves["underlying_returns"][-1] if moves["underlying_returns"] else None
        out[f"underlying_{horizon}d"] = und
        out[f"short_{horizon}d"] = None if und is None else -und
        out[f"mae_{horizon}d"] = moves["mae"]
        out[f"mfe_{horizon}d"] = moves["mfe"]
    return out


def summarize(signals, prefix="short"):
    result = {"n": len(signals)}
    for horizon in HORIZONS:
        key = f"{prefix}_{horizon}d"
        values = [row[key] for row in signals if row.get(key) is not None]
        result[f"{key}_n"] = len(values)
        if not values:
            result[f"{key}_mean"] = None
            result[f"{key}_median"] = None
            result[f"{key}_win_rate"] = None
            result[f"{key}_expected_value"] = None
            result[f"{key}_profit_factor"] = None
            continue
        wins = [v for v in values if v > 0]
        losses = [v for v in values if v < 0]
        result[f"{key}_mean"] = statistics.fmean(values)
        result[f"{key}_median"] = statistics.median(values)
        result[f"{key}_win_rate"] = len(wins) / len(values)
        result[f"{key}_expected_value"] = statistics.fmean(values)
        gross_win, gross_loss = sum(wins), abs(sum(losses))
        result[f"{key}_profit_factor"] = None if gross_loss == 0 else gross_win / gross_loss
        mae = [row[f"mae_{horizon}d"] for row in signals if row.get(f"mae_{horizon}d") is not None]
        mfe = [row[f"mfe_{horizon}d"] for row in signals if row.get(f"mfe_{horizon}d") is not None]
        result[f"mae_{horizon}d_median"] = statistics.median(mae) if mae else None
        result[f"mae_{horizon}d_max"] = max(mae) if mae else None
        result[f"mfe_{horizon}d_median"] = statistics.median(mfe) if mfe else None
        result[f"mfe_{horizon}d_max"] = max(mfe) if mfe else None
        und = [row[f"underlying_{horizon}d"] for row in signals if row.get(f"underlying_{horizon}d") is not None]
        result[f"underlying_{horizon}d_mean"] = statistics.fmean(und) if und else None
        result[f"underlying_{horizon}d_median"] = statistics.median(und) if und else None
    return result


def run_variant(name, pairs, exposures, prices, sec, spy_history, *, top_n, sparse, scorer, mapping_mode="fixed", entry_mode="CLOSE_SIGNAL"):
    monthly = []
    signals = []
    skipped_open = 0
    for pair in pairs:
        universe = universe_for(pair, exposures, top_n=top_n, mapping_mode=mapping_mode, sparse=sparse)
        mapped = len({seed["ticker"] for seed in universe["seeds"]})
        deterioration = 0
        watches = 0
        triggered = 0
        seen_deterioration = set()
        watched = set()
        entered = set()
        decision = pair["available_at"]
        spy_month = closes_as_of(spy_history, pair["next_available"] - timedelta(seconds=1))
        session_days = [parse_datetime(row["available_at"]) for row in spy_month if parse_datetime(row["available_at"]) >= decision]
        for ticker, seeds in universe["by_ticker"].items():
            seed = primary_seed(seeds)
            themes = [{"industry": item.get("industry"), "ism_rank": item.get("ism_rank"), "report_type": item.get("report_type")} for item in seeds]
            history = prices.get(ticker) or {"records": []}
            sector_hist = prices.get(seed.get("sector_etf") or "") or {"records": []}
            bundle = sec.get(ticker)
            for now in session_days:
                bars = closes_as_of(history, now)
                sector_bars = closes_as_of(sector_hist, now)
                spy_bars = closes_as_of(spy_history, now)
                if len(bars) < 21:
                    continue
                funds = fundamentals_as_of(bundle, now)
                cats = catalysts_as_of(bundle, now)
                row = snapshot_row(seed, bars, sector_bars, spy_bars, funds, cats, now, themes=themes)
                scored = scorer(row)
                if scored.get("factors", {}).get("company_deterioration") or scored.get("factors", {}).get("company_fundamentals"):
                    if ticker not in seen_deterioration:
                        deterioration += 1
                        seen_deterioration.add(ticker)
                if scored.get("state") in {"WATCH", "ARMED", "TRIGGERED"} and ticker not in watched:
                    watches += 1
                    watched.add(ticker)
                if ticker in entered or not scored.get("selected"):
                    continue
                future = [bar for bar in history.get("records", []) if bar["date"] > bars[-1]["date"]]
                entry, window, used_mode = entry_window(bars, future, mode=entry_mode)
                if entry is None:
                    skipped_open += 1
                    continue
                stats = forward_stats(entry, window)
                bearish = [item for item in (row.get("catalysts") or []) if str(item.get("direction") or "").upper() == "BEARISH"]
                signal = {
                    "variant": name,
                    "ticker": ticker,
                    "reference_month": pair["reference_month"],
                    "decision_time": now.isoformat(),
                    "entry_mode": used_mode,
                    "industry": seed.get("industry"),
                    "ism_rank": seed.get("ism_rank"),
                    "report_type": seed.get("report_type"),
                    "themes": themes,
                    "state": scored.get("state"),
                    "relative_vs_sector": row["relative_vs_sector"],
                    "relative_vs_market": row["relative_vs_market"],
                    "eps_revision": row["eps_revision_30d"],
                    "revenue_revision": row["revenue_revision_30d"],
                    "cash_flow_quality": (row.get("cash_flow_quality") or {}).get("state"),
                    "catalyst": (bearish[0]["type"] if bearish else None),
                    "catalyst_direction": (bearish[0]["direction"] if bearish else None),
                    "technical_breakdown": row["technical_breakdown"],
                    "failed_retest": row["failed_retest"],
                    "regime": row["regime"],
                    "entry": entry,
                    "invalidation": row["invalidation"],
                    "target": row["target"],
                    "reward_to_risk": (row.get("risk_reward") or {}).get("reward_to_risk"),
                    "eps_growth": row.get("eps_growth"),
                    **stats,
                }
                signals.append(signal)
                triggered += 1
                entered.add(ticker)
                break
        monthly.append({
            "month": pair["reference_month"],
            "available_at": pair["available_at"].isoformat(),
            "manufacturing": [row["industry"] for row in select_contracting_industries(pair["manufacturing"]["contracting"])],
            "services": [row["industry"] for row in select_contracting_industries(pair["services"]["contracting"])],
            "mapped_stocks": mapped,
            "unmapped": universe["unmapped"],
            "deterioration": deterioration,
            "watch": watches,
            "triggered": triggered,
        })
    summary = summarize(signals)
    summary["skipped_missing_open"] = skipped_open
    attributed = theme_attribution(signals)
    return {
        "name": name,
        "summary": summary,
        "monthly": monthly,
        "signals": signals,
        "industries": attributed["industries"],
        "theme_attribution_note": attributed["note"],
        "entry_mode": entry_mode,
    }


def compact_summary(summary):
    out = {"n": summary.get("n")}
    for horizon in HORIZONS:
        out[f"{horizon}d_mean"] = summary.get(f"short_{horizon}d_mean")
        out[f"{horizon}d_median"] = summary.get(f"short_{horizon}d_median")
        out[f"{horizon}d_win_rate"] = summary.get(f"short_{horizon}d_win_rate")
        out[f"{horizon}d_profit_factor"] = summary.get(f"short_{horizon}d_profit_factor")
        out[f"{horizon}d_n"] = summary.get(f"short_{horizon}d_n")
        out[f"mae_{horizon}d_median"] = summary.get(f"mae_{horizon}d_median")
        out[f"mae_{horizon}d_max"] = summary.get(f"mae_{horizon}d_max")
        out[f"mfe_{horizon}d_median"] = summary.get(f"mfe_{horizon}d_median")
        out[f"mfe_{horizon}d_max"] = summary.get(f"mfe_{horizon}d_max")
    return out


def delta(left, right, key):
    a, b = left.get(key), right.get(key)
    if a is None or b is None:
        return None
    return b - a


def main():
    reports = load_reports()
    exposures = load_exposures()
    pairs = report_pairs(reports)
    tickers = {"SPY"}
    for rows in exposures.values():
        for row in rows:
            tickers.add(row["ticker"])
            if row.get("sector_etf"):
                tickers.add(row["sector_etf"])
    CACHE.mkdir(parents=True, exist_ok=True)
    yahoo = httpx.Client(timeout=20, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
    sec_http = httpx.Client(timeout=20, headers={
        "User-Agent": "Rocket Research AdminContact@example.com",
        "Accept-Encoding": "gzip, deflate",
    }, follow_redirects=True)
    prices = {}
    try:
        print(f"loading prices for {len(tickers)} tickers", flush=True)
        for ticker in sorted(tickers):
            prices[ticker] = fetch_price(ticker, yahoo)
            time.sleep(0.05)
        equity_tickers = sorted(t for t in tickers if t not in {"SPY", "XLI", "XLB", "XLK", "XLE", "XLY", "XLP", "XLF", "XLC", "XLRE", "XLV"})
        print(f"loading SEC bundles for {len(equity_tickers)} tickers", flush=True)
        sec = load_sec_bundle(equity_tickers, sec_http)
        print("loading tokenized snapshot", flush=True)
        tokenized = acquire_tokenized_snapshot(http=yahoo, now=END)
    finally:
        yahoo.close()
        sec_http.close()

    def v2(**kwargs):
        return lambda row: score_shorts_v2(row, **kwargs)

    common = {"pairs": pairs, "exposures": exposures, "prices": prices, "sec": sec, "spy_history": prices["SPY"]}
    variant_specs = [
        ("A0_PRODUCTION", dict(top_n=None, sparse=True, scorer=score_ism_short_candidate)),
        ("A1_EXPANDED_ONLY", dict(top_n=None, sparse=False, scorer=score_ism_short_candidate)),
        ("A2_TOP3_ONLY", dict(top_n=3, sparse=False, scorer=score_ism_short_candidate)),
        ("A3_TOP3_RELATIVE", dict(top_n=3, sparse=False, scorer=v2(deterioration_mode="fundamentals", relative_threshold=0.0))),
        ("A4_TOP3_RELATIVE_CASHFLOW", dict(top_n=3, sparse=False, scorer=v2(deterioration_mode="cashflow_required", relative_threshold=0.0))),
        ("A5_TOP3_RELATIVE_CATALYST", dict(top_n=3, sparse=False, scorer=v2(deterioration_mode="cashflow_required", relative_threshold=0.0, require_bearish_catalyst=True))),
        ("A6_FULL_V2", dict(top_n=3, sparse=False, scorer=v2(deterioration_mode="any", relative_threshold=0.0))),
        ("A0_NEXT_OPEN", dict(top_n=None, sparse=True, scorer=score_ism_short_candidate, entry_mode="NEXT_SESSION_OPEN")),
        ("A3_NEXT_OPEN", dict(top_n=3, sparse=False, scorer=v2(deterioration_mode="fundamentals", relative_threshold=0.0), entry_mode="NEXT_SESSION_OPEN")),
        ("A6_NEXT_OPEN", dict(top_n=3, sparse=False, scorer=v2(deterioration_mode="any", relative_threshold=0.0), entry_mode="NEXT_SESSION_OPEN")),
        ("E_rr_1_5", dict(top_n=3, sparse=False, scorer=v2(deterioration_mode="any", relative_threshold=0.0, rr_min=1.5))),
        ("E_rr_2_0", dict(top_n=3, sparse=False, scorer=v2(deterioration_mode="any", relative_threshold=0.0, rr_min=2.0))),
        ("E_rr_2_5", dict(top_n=3, sparse=False, scorer=v2(deterioration_mode="any", relative_threshold=0.0, rr_min=2.5))),
        ("strict_pit_mappings", dict(top_n=3, sparse=False, scorer=v2(), mapping_mode="strict_pit")),
    ]
    variants = {}
    for name, kwargs in variant_specs:
        print(f"running {name}", flush=True)
        variants[name] = run_variant(name, **common, **kwargs)

    current_names = sorted({seed["ticker"] for seed in universe_for(pairs[-1], exposures, top_n=3)["seeds"]}) if pairs else []
    token_rows = list(tokenized.records)
    executable_now = []
    executable_instruments = {}
    for ticker in current_names:
        row = eligibility(ticker, token_rows, now=END)
        if row["execution"]["status"] == "EXECUTION_ELIGIBLE":
            executable_now.append(ticker)
            executable_instruments[ticker] = [
                {"venue": item.get("venue"), "symbol": item.get("token_symbol"), "type": item.get("instrument_type")}
                for item in row["execution"]["instruments"]
            ]

    production = variants["A0_PRODUCTION"]["summary"]
    expanded = variants["A1_EXPANDED_ONLY"]["summary"]
    v2_core = variants["A3_TOP3_RELATIVE"]["summary"]
    live_v2 = variants["A6_FULL_V2"]["summary"]
    classified = classify_shorts_v2_edge(production=production, core=v2_core, live=live_v2)

    comparisons = {
        "production_to_expanded": {
            "question": "Did expanding the universe improve coverage?",
            "from": "A0_PRODUCTION",
            "to": "A1_EXPANDED_ONLY",
            "from_n": production["n"],
            "to_n": expanded["n"],
            "short_5d_mean_delta": delta(production, expanded, "short_5d_mean"),
            "short_20d_mean_delta": delta(production, expanded, "short_20d_mean"),
            "mae_20d_median_delta": delta(production, expanded, "mae_20d_median"),
        },
        "expanded_to_v2": {
            "question": "Did changing the strategy improve signal quality versus the expanded current gate?",
            "from": "A1_EXPANDED_ONLY",
            "to": "A3_TOP3_RELATIVE",
            "from_n": expanded["n"],
            "to_n": v2_core["n"],
            "short_5d_mean_delta": delta(expanded, v2_core, "short_5d_mean"),
            "short_20d_mean_delta": delta(expanded, v2_core, "short_20d_mean"),
            "mae_20d_median_delta": delta(expanded, v2_core, "mae_20d_median"),
        },
        "production_to_v2": {
            "question": "Did core A3 improve signal quality versus the production baseline?",
            "from": "A0_PRODUCTION",
            "to": "A3_TOP3_RELATIVE",
            "from_n": production["n"],
            "to_n": v2_core["n"],
            "short_5d_mean_delta": delta(production, v2_core, "short_5d_mean"),
            "short_20d_mean_delta": delta(production, v2_core, "short_20d_mean"),
            "mae_20d_median_delta": delta(production, v2_core, "mae_20d_median"),
        },
        "production_to_live_v2": {
            "question": "Did live Shorts v2 (A6) improve signal quality versus the production baseline?",
            "from": "A0_PRODUCTION",
            "to": "A6_FULL_V2",
            "from_n": production["n"],
            "to_n": live_v2["n"],
            "short_5d_mean_delta": delta(production, live_v2, "short_5d_mean"),
            "short_20d_mean_delta": delta(production, live_v2, "short_20d_mean"),
            "mae_20d_median_delta": delta(production, live_v2, "mae_20d_median"),
        },
        "close_vs_next_open_production": {
            "close": compact_summary(production),
            "next_open": compact_summary(variants["A0_NEXT_OPEN"]["summary"]),
            "short_5d_mean_delta": delta(production, variants["A0_NEXT_OPEN"]["summary"], "short_5d_mean"),
            "mae_20d_median_delta": delta(production, variants["A0_NEXT_OPEN"]["summary"], "mae_20d_median"),
            "mfe_20d_median_delta": delta(production, variants["A0_NEXT_OPEN"]["summary"], "mfe_20d_median"),
        },
        "close_vs_next_open_v2": {
            "close": compact_summary(v2_core),
            "next_open": compact_summary(variants["A3_NEXT_OPEN"]["summary"]),
            "short_5d_mean_delta": delta(v2_core, variants["A3_NEXT_OPEN"]["summary"], "short_5d_mean"),
            "mae_20d_median_delta": delta(v2_core, variants["A3_NEXT_OPEN"]["summary"], "mae_20d_median"),
            "mfe_20d_median_delta": delta(v2_core, variants["A3_NEXT_OPEN"]["summary"], "mfe_20d_median"),
        },
    }

    payload = {
        "as_of": END.isoformat(),
        "months": [pair["reference_month"] for pair in pairs],
        "mapping_mode": "fixed unless named strict_pit",
        "estimate_revisions": "HISTORICALLY_UNAVAILABLE",
        "tokenized_historical": (
            "Kraken openingDate is listing_at only; available_at equals observed_at. "
            "Present snapshots never backfill historical shortability. "
            "xStocks/Ondo spot and Ondo perps are present-tense."
        ),
        "tokenized_current_research_names": current_names,
        "tokenized_current_execution_eligible": executable_now,
        "tokenized_current_instruments": executable_instruments,
        "tokenized_current_source": tokenized.source,
        "tokenized_provider_attempts": tokenized.extras.get("provider_attempts"),
        "comparisons": comparisons,
        "variants": {name: {k: v for k, v in row.items() if k != "signals"} | {"signal_count": len(row["signals"]), "attributions": row["signals"][:80]}
                     for name, row in variants.items()},
        "theme_attribution_note": variants["A6_FULL_V2"].get("theme_attribution_note"),
        "limitations": (
            "FMP/Massive keys were not present in this run, so live-style estimate revisions could not be reconstructed. "
            "SEC 10-K facts supply reported EPS/cash-flow quality with filing dates. "
            "Yahoo daily availability is approximated as NYSE session close; next-session open uses the following bar's open. "
            "Industry mappings were reviewed in September 2026; Backtest 1 applies them historically as a labeled fixed-universe test. "
            "Generic 8-K items are context unless the item itself is a structured bearish event (2.06, 4.02) or earnings actual < estimate. "
            "Borrow fees, funding as P&L, and squeeze metrics were UNKNOWN. "
            "Theme attribution is non-additive: one trade may appear in multiple theme buckets."
        ),
        "infrastructure_assessment": classified["infrastructure_assessment"],
        "core_edge_assessment": classified["core_edge_assessment"],
        "live_v2_edge_assessment": classified["live_v2_edge_assessment"],
        "edge_assessment": classified["edge_assessment"],
        "assessment": classified["edge_assessment"],
        "live_v2_n": live_v2["n"],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    a4 = variants["A4_TOP3_RELATIVE_CASHFLOW"]["summary"]
    print(json.dumps({
        "core_edge_assessment": classified["core_edge_assessment"],
        "live_v2_edge_assessment": classified["live_v2_edge_assessment"],
        "edge_assessment": classified["edge_assessment"],
        "infrastructure_assessment": classified["infrastructure_assessment"],
        "months": payload["months"],
        "A0_n": production["n"],
        "A1_n": expanded["n"],
        "A3_n": v2_core["n"],
        "A4_n": a4["n"],
        "A6_n": live_v2["n"],
        "A0_short_5_10_20": [production.get("short_5d_mean"), production.get("short_10d_mean"), production.get("short_20d_mean")],
        "A3_short_5_10_20": [v2_core.get("short_5d_mean"), v2_core.get("short_10d_mean"), v2_core.get("short_20d_mean")],
        "A4_short_5_10_20": [a4.get("short_5d_mean"), a4.get("short_10d_mean"), a4.get("short_20d_mean")],
        "A6_short_5_10_20": [live_v2.get("short_5d_mean"), live_v2.get("short_10d_mean"), live_v2.get("short_20d_mean")],
        "executable_now": executable_now,
        "json": str(OUT_JSON),
    }, indent=2))


if __name__ == "__main__":
    main()
