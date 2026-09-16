#!/usr/bin/env python3
"""Point-in-time Shorts v2 backtest. Research only; never uses current snapshots as history."""

from __future__ import annotations

import json
import math
import statistics
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from rocket.config import DEFAULT_CONFIG_DIR
from rocket.pit import parse_datetime
from rocket.providers.historical_prices import bars_eligible_at, daily_bars
from rocket.providers.ism_universe import build_short_universe, select_contracting_industries
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
from rocket.workflows.shorts import score_ism_short_candidate, score_shorts_v2

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
    def load():
        try:
            return daily_bars(ticker, http=client, range="2y")
        except Exception as exc:
            return {"source": "unavailable", "error": type(exc).__name__, "records": []}
    return cache_json(CACHE / "prices" / f"{ticker}.json", load)


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


def snapshot_row(seed, bars, sector_bars, spy_bars, fundamentals, catalysts, now):
    closes = series_from(bars)
    sector = series_from(sector_bars)
    spy = series_from(spy_bars)
    relative = relative_strength(closes, sector, spy)
    retest = failed_retest(closes)
    regime = classify_regime(spy, sector)
    price = closes[-1] if closes else None
    target = history_target(closes)
    stop = prior_session_high(closes)
    row = {
        "ticker": seed["ticker"],
        "asset": seed["ticker"],
        "candidate_sources": [{
            "direction": "short",
            "industry": seed.get("industry"),
            "rank": seed.get("ism_rank"),
            "report_type": seed.get("report_type"),
            "thesis": f"ISM {seed.get('reference_month')} {seed.get('report_type')}: {seed.get('industry')} contracting",
        }],
        "candidate_id": f"listed:{seed['ticker']}",
        "industry": seed.get("industry"),
        "ism_rank": seed.get("ism_rank"),
        "report_type": seed.get("report_type"),
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


def forward_stats(entry_bar, future, horizons=HORIZONS):
    entry = _finite(entry_bar.get("close"))
    if entry is None:
        return {}
    out = {}
    for horizon in horizons:
        window = future[:horizon]
        if len(window) < horizon:
            out[f"underlying_{horizon}d"] = None
            out[f"short_{horizon}d"] = None
            out[f"mae_{horizon}d"] = None
            out[f"mfe_{horizon}d"] = None
            continue
        highs = [row.get("high") if row.get("high") is not None else row.get("close") for row in window]
        lows = [row.get("low") if row.get("low") is not None else row.get("close") for row in window]
        closes = [row.get("close") for row in window]
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


def run_variant(name, pairs, exposures, prices, sec, spy_history, *, top_n, sparse, scorer, mapping_mode="fixed"):
    monthly = []
    signals = []
    attributions = []
    for pair in pairs:
        universe = universe_for(pair, exposures, top_n=top_n, mapping_mode=mapping_mode, sparse=sparse)
        mapped = len({seed["ticker"] for seed in universe["seeds"]})
        deterioration = 0
        watches = 0
        triggered = 0
        seen = set()
        decision = pair["available_at"]
        spy_month = closes_as_of(spy_history, pair["next_available"] - timedelta(seconds=1))
        session_days = [parse_datetime(row["available_at"]) for row in spy_month if parse_datetime(row["available_at"]) >= decision]
        month_rows = []
        for seed in universe["seeds"]:
            ticker = seed["ticker"]
            history = prices.get(ticker) or {"records": []}
            sector_hist = prices.get(seed.get("sector_etf") or "") or {"records": []}
            bundle = sec.get(ticker)
            entered = False
            for now in session_days:
                bars = closes_as_of(history, now)
                sector_bars = closes_as_of(sector_hist, now)
                spy_bars = closes_as_of(spy_history, now)
                if len(bars) < 21:
                    continue
                funds = fundamentals_as_of(bundle, now)
                cats = catalysts_as_of(bundle, now)
                row = snapshot_row(seed, bars, sector_bars, spy_bars, funds, cats, now)
                scored = scorer(row)
                if scored.get("factors", {}).get("company_deterioration") or scored.get("factors", {}).get("company_fundamentals"):
                    if ticker not in seen:
                        deterioration += 1
                        seen.add(ticker)
                if scored.get("state") in {"WATCH", "ARMED", "TRIGGERED"} and ticker not in {r["ticker"] for r in month_rows if r.get("watched")}:
                    watches += 1
                    month_rows.append({"ticker": ticker, "watched": True})
                if entered or not scored.get("selected"):
                    continue
                future = [bar for bar in history.get("records", []) if bar["date"] > bars[-1]["date"]]
                stats = forward_stats(bars[-1], future)
                signal = {
                    "variant": name,
                    "ticker": ticker,
                    "reference_month": pair["reference_month"],
                    "decision_time": now.isoformat(),
                    "industry": seed.get("industry"),
                    "ism_rank": seed.get("ism_rank"),
                    "report_type": seed.get("report_type"),
                    "state": scored.get("state"),
                    "relative_vs_sector": row["relative_vs_sector"],
                    "relative_vs_market": row["relative_vs_market"],
                    "eps_revision": row["eps_revision_30d"],
                    "revenue_revision": row["revenue_revision_30d"],
                    "cash_flow_quality": (row.get("cash_flow_quality") or {}).get("state"),
                    "catalyst": (row["catalysts"][0]["type"] if row["catalysts"] else None),
                    "technical_breakdown": row["technical_breakdown"],
                    "failed_retest": row["failed_retest"],
                    "regime": row["regime"],
                    "entry": row["current_price"],
                    "invalidation": row["invalidation"],
                    "target": row["target"],
                    "reward_to_risk": (row.get("risk_reward") or {}).get("reward_to_risk"),
                    "eps_growth": row.get("eps_growth"),
                    **stats,
                }
                signals.append(signal)
                attributions.append(signal)
                triggered += 1
                entered = True
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
    industry_pnl = defaultdict(list)
    for row in signals:
        if row.get("short_20d") is not None:
            industry_pnl[f"{row.get('report_type')}:{row.get('industry')}"].append(row["short_20d"])
    industries = {
        key: {"n": len(vals), "mean_short_20d": statistics.fmean(vals), "median_short_20d": statistics.median(vals)}
        for key, vals in sorted(industry_pnl.items())
    }
    return {"name": name, "summary": summary, "monthly": monthly, "signals": signals, "industries": industries}


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
        for ticker in sorted(tickers):
            prices[ticker] = fetch_price(ticker, yahoo)
            time.sleep(0.05)
        sec = load_sec_bundle(sorted(t for t in tickers if t not in {"SPY", "XLI", "XLB", "XLK", "XLE", "XLY", "XLP", "XLF", "XLC", "XLRE", "XLV"}), sec_http)
        tokenized = acquire_tokenized_snapshot(http=yahoo, now=END)
    finally:
        yahoo.close()
        sec_http.close()

    def v2(**kwargs):
        return lambda row: score_shorts_v2(row, **kwargs)

    def catalyst_required(row):
        scored = score_shorts_v2(row)
        if scored["selected"] and not row.get("catalysts"):
            scored = {**scored, "selected": False, "state": "WATCH", "rejection_reason": "catalyst_missing"}
        return scored

    variants = {
        "A_current_all_contracting_expanded": run_variant(
            "A_current_all_contracting_expanded", pairs, exposures, prices, sec, prices["SPY"],
            top_n=None, sparse=False, scorer=score_ism_short_candidate,
        ),
        "A_current_sparse_original_names": run_variant(
            "A_current_sparse_original_names", pairs, exposures, prices, sec, prices["SPY"],
            top_n=None, sparse=True, scorer=score_ism_short_candidate,
        ),
        "B_top3_relative0_fundamentals_breakdown": run_variant(
            "B_top3_relative0_fundamentals_breakdown", pairs, exposures, prices, sec, prices["SPY"],
            top_n=3, sparse=False, scorer=v2(relative_threshold=0.0, require_failed_retest=False),
        ),
        "B_relative_neg5pct": run_variant(
            "B_relative_neg5pct", pairs, exposures, prices, sec, prices["SPY"],
            top_n=3, sparse=False, scorer=v2(relative_threshold=-0.05, require_failed_retest=False),
        ),
        "B_breakdown_and_failed_retest": run_variant(
            "B_breakdown_and_failed_retest", pairs, exposures, prices, sec, prices["SPY"],
            top_n=3, sparse=False, scorer=v2(relative_threshold=0.0, require_failed_retest=True),
        ),
        "C_revisions_historically_unavailable": run_variant(
            "C_revisions_historically_unavailable", pairs, exposures, prices, sec, prices["SPY"],
            top_n=3, sparse=False, scorer=v2(relative_threshold=0.0),
        ),
        "D_catalyst_required": run_variant(
            "D_catalyst_required", pairs, exposures, prices, sec, prices["SPY"],
            top_n=3, sparse=False, scorer=catalyst_required,
        ),
        "E_regime_and_rr_1_5": run_variant(
            "E_regime_and_rr_1_5", pairs, exposures, prices, sec, prices["SPY"],
            top_n=3, sparse=False, scorer=v2(relative_threshold=0.0, rr_min=1.5),
        ),
        "E_rr_2_0": run_variant(
            "E_rr_2_0", pairs, exposures, prices, sec, prices["SPY"],
            top_n=3, sparse=False, scorer=v2(relative_threshold=0.0, rr_min=2.0),
        ),
        "E_rr_2_5": run_variant(
            "E_rr_2_5", pairs, exposures, prices, sec, prices["SPY"],
            top_n=3, sparse=False, scorer=v2(relative_threshold=0.0, rr_min=2.5),
        ),
        "strict_pit_mappings": run_variant(
            "strict_pit_mappings", pairs, exposures, prices, sec, prices["SPY"],
            top_n=3, sparse=False, scorer=v2(), mapping_mode="strict_pit",
        ),
    }

    # Tokenized overlay is current-only.
    current_names = sorted({seed["ticker"] for seed in universe_for(pairs[-1], exposures, top_n=3)["seeds"]}) if pairs else []
    token_rows = list(tokenized.records)
    executable_now = []
    for ticker in current_names:
        row = eligibility(ticker, token_rows, now=END)
        if row["execution"]["status"] == "EXECUTION_ELIGIBLE":
            executable_now.append(ticker)

    a = variants["A_current_all_contracting_expanded"]["summary"]
    b = variants["B_top3_relative0_fundamentals_breakdown"]["summary"]
    assessment = "PROMISING_BUT_INSUFFICIENT_SAMPLE"
    if a["n"] == 0 and b["n"] == 0:
        assessment = "EDGE_NOT_VALIDATED"
    elif b["n"] >= 8 and (b.get("short_20d_mean") or 0) > (a.get("short_20d_mean") or 0) + 0.01 and (b.get("mae_20d_median") or 1) <= (a.get("mae_20d_median") or 1) + 0.02:
        assessment = "IMPROVED_HISTORICAL_SIGNAL"
    elif b["n"] >= 8 and (b.get("short_20d_mean") or 0) < (a.get("short_20d_mean") or 0) - 0.01:
        assessment = "REGRESSION"
    else:
        assessment = "PROMISING_BUT_INSUFFICIENT_SAMPLE" if b["n"] or a["n"] else "EDGE_NOT_VALIDATED"
    # Small sample overrides deployable-sounding labels.
    if assessment == "IMPROVED_HISTORICAL_SIGNAL" and (a["n"] + b["n"]) < 30:
        assessment = "PROMISING_BUT_INSUFFICIENT_SAMPLE"

    payload = {
        "as_of": END.isoformat(),
        "months": [pair["reference_month"] for pair in pairs],
        "mapping_mode": "fixed unless named strict_pit",
        "estimate_revisions": "HISTORICALLY_UNAVAILABLE",
        "tokenized_historical": "HISTORICALLY_UNAVAILABLE",
        "tokenized_current_research_names": current_names,
        "tokenized_current_execution_eligible": executable_now,
        "tokenized_current_source": tokenized.source,
        "variants": {name: {k: v for k, v in row.items() if k != "signals"} | {"signal_count": len(row["signals"]), "attributions": row["signals"][:80]}
                     for name, row in variants.items()},
        "limitations": (
            "FMP/Massive keys were not present in this run, so live-style estimate revisions could not be reconstructed. "
            "SEC 10-K facts supply reported EPS/cash-flow quality with filing dates. "
            "Yahoo daily availability is approximated as NYSE session close. "
            "Industry mappings were reviewed in September 2026; Backtest 1 applies them historically as a labeled fixed-universe test. "
            "xStocks/ONDO listings observed at run time are not used as January 2026 short availability. "
            "Borrow fees, funding, and squeeze metrics were UNKNOWN."
        ),
        "assessment": assessment,
    }
    # Keep JSON modest: drop bulky monthly unmapped lists if huge
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(json.dumps({
        "assessment": assessment,
        "months": payload["months"],
        "A_n": a["n"],
        "B_n": b["n"],
        "A_short_5_10_20": [a.get("short_5d_mean"), a.get("short_10d_mean"), a.get("short_20d_mean")],
        "B_short_5_10_20": [b.get("short_5d_mean"), b.get("short_10d_mean"), b.get("short_20d_mean")],
        "executable_now": executable_now,
        "json": str(OUT_JSON),
    }, indent=2))


if __name__ == "__main__":
    main()
