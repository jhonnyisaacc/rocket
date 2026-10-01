"""Markdown report. Numbers come from the backtest dict; this file does not fetch data."""

from __future__ import annotations

from typing import Any

ASSUMPTIONS = (
    "Read-only research. Nothing here is an order, a target weight to send to a venue, or a claim of a tradable edge.",
    "Same-close fills. The decision for session T can use the session T close, and the fill is that close plus slippage. Stops are daily-close stops; a wick through the stop is invisible.",
    "No look-ahead. Every read goes through an as-of view. Credit OAS and effective fed funds are lagged one calendar day. Treasury yields, equities, VIX, oil, the dollar, gold, bitcoin, DVOL and funding use the same close. That is slightly generous for yields that print in the afternoon.",
    "MOVE is not on a free historical feed. The volatility pillar uses VIX plus the 20-session annualized realized volatility of TLT, and the thresholds are in TLT-vol units.",
    "Credit prefers FRED BAMLH0A0HYM2 (and IG OAS when it is present). If the OAS series is missing, the 20-session HYG/LQD return is the fallback and is labeled as such.",
    "The dollar series is ICE DXY when Yahoo has it, otherwise the broad trade-weighted dollar. Oil is FRED spot when the download succeeds, otherwise the front-month future.",
    "BTC options are Black-Scholes. Implied vol is Deribit DVOL when that day's print exists, otherwise trailing realized vol. These are not historical Deribit trade prices. DVOL is a 30-day index applied to a 60-day, 15 percent out-of-the-money put. Entry IV is worsened by the configured slippage.",
    "Perp funding is the sum of Deribit BTC-PERPETUAL hourly interest_1h, in fraction of notional. Positive funding is paid by longs. A short does not also buy puts unless put_with_short is turned on.",
    "The equity book is long-only and unlevered. USDC earns nothing in the simulation. Prices are split- and dividend-adjusted closes, so dividends are in the path rather than paid as cash. Ondo tokenized stocks are the underlying one-for-one. Sessions before the configured Ondo date are a proxy and are reported as their own window. Equity slippage is charged on every fill, including the opening buys of the strategy and the benchmarks.",
    "Porto rules. Cash target is 35, 40 or 45 percent in risk-on, neutral and risk-off. An up day in the index raises the target by one step, capped at 45 percent. Adds are only ETN, CAT, APH and AMAT, only in the bottom half of the trailing buy zone, and never in risk-off, on an FOMC decision date, or on an oil-shock day. Trims follow TSLA, FCX, BAC, then half of META, EQIX and MSFT, then a light AMZN trim. A name that is down on the day is not sold. Nothing is sold on a hard-down index day. Two of the three trim gates must pass; on daily bars the regular-hours gate always passes. There is no daily rebalance back to equal weight.",
    "The regime can block adds and move the cash target. It does not authorize selling into a red name or a hard-down day.",
    "Parameters live in config/market_check.toml. They were set from the stated rules and from round level thresholds, and they were not searched against this result. The out-of-sample split is the second half of the window, same parameters.",
    "Phillip's private numeric bands are not in the repo. The daily check uses the bottom quartile of the trailing range and shifts it with the regime. That is a stand-in.",
    "The September 2026 book snapshot is printed for context. There is no cost basis before 15 September 2026, so the backtest does not replay that book. An optional trade-log CSV is only a comparison.",
    "One path, one parameter set, and real approximation error on options, funding and same-close fills. A better in-sample number would not, by itself, be evidence to size up.",
)


def _pct(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{value:.1%}"


def _num(value: Any, digits: int = 2) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{value:.{digits}f}"


def _line(stats: dict[str, Any] | None) -> str:
    if not stats:
        return "n/a"
    return (
        f"{_pct(stats.get('cagr'))} CAGR, {_pct(stats.get('max_drawdown'))} max DD, "
        f"{_pct(stats.get('volatility'))} vol, {_num(stats.get('sharpe'))} Sharpe, "
        f"{_pct(stats.get('total_return'))} total"
    )


def _monthly_table(block: dict[str, Any]) -> str:
    strategy = {row["month"]: row["return"] for row in block["monthly"]["strategy"]}
    bench = {row["month"]: row["return"] for row in block["monthly"]["equal_weight"]}
    spy = {row["month"]: row["return"] for row in block["monthly"]["spy"]}
    lines = ["| Month | Strategy | Equal-weight | SPY |", "|---|---:|---:|---:|"]
    for month, value in strategy.items():
        lines.append(f"| {month} | {_pct(value)} | {_pct(bench.get(month))} | {_pct(spy.get(month))} |")
    return "\n".join(lines)


def _window_block(title: str, block: dict[str, Any]) -> str:
    return "\n".join([
        f"### {title}",
        "",
        f"- Strategy: {_line(block['strategy'])}",
        f"- Equal-weight buy-and-hold: {_line(block['equal_weight'])}",
        f"- SPY: {_line(block['spy'])}",
        f"- QQQ (extra): {_line(block['qqq'])}",
        "",
        _monthly_table(block),
    ])


def _deriv_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Month | Signal | Position | Entry | Exit | P&L | Success |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {month} | {regime} / {signal} | {position} {size:g} {hedge} | {entry:.0f} | {exit:.0f} | {pnl:.2%} | {success} |".format(
                month=row["month"],
                regime=row["regime"],
                signal=row["signal"],
                position=row["position"],
                size=row["size"],
                hedge=("+put" if row["hedge"] == "btc_puts" else ""),
                entry=row["entry"],
                exit=row["exit"],
                pnl=row["pnl"],
                success="n/a" if row["success"] is None else ("yes" if row["success"] else "no"),
            )
        )
    return "\n".join(lines)


def _summary_line(stats: dict[str, Any]) -> str:
    return (
        f"hit rate {_pct(stats.get('hit_rate'))} on {stats.get('active_months')} active months, "
        f"sum of monthly P&L {_pct(stats.get('sum_pnl'))}, "
        f"worst {_pct(stats.get('worst_pnl'))}, best {_pct(stats.get('best_pnl'))}, "
        f"perp hit rate {_pct(stats.get('perp_hit_rate'))}, "
        f"put hit rate {_pct(stats.get('hedge_hit_rate'))}, "
        f"stops {stats.get('stopped')}"
    )


def render_report(result: dict[str, Any]) -> str:
    portfolio = result["portfolio"]
    derivatives = result["derivatives"]
    meta = result.get("meta") or {}
    counts = portfolio["trades_by_name"]
    count_line = ", ".join(
        f"{name} {bucket.get('buy', 0)} buys/{bucket.get('sell', 0)} sells"
        for name, bucket in sorted(counts.items())
    ) or "none"
    comparison = result.get("trade_log") or []
    if comparison:
        compared = "; ".join(
            f"{row['date']} {row['side']} {row['ticker']} {'matched ' + ','.join(row['simulated_dates']) if row['matched'] else 'not matched'}"
            for row in comparison
        )
    else:
        compared = "No trade log was supplied beyond the snapshot note."
    book = result.get("current_book") or {}
    weights = book.get("weights") or {}
    weight_line = ", ".join(f"{name} {value:.1%}" for name, value in weights.items()) or "n/a"
    lines = [
        "# Market-check backtest",
        "",
        (
            f"Window {portfolio['start']} to {portfolio['end']} ({portfolio['sessions']} equity sessions). "
            f"Out-of-sample starts {result['oos_start']}. Ondo proxy before {portfolio['ondo_live']}."
        ),
        "",
        "This is a research record of one rule set on one history. It is not a forecast and not an instruction to trade.",
        "",
        "## Portfolio",
        "",
        (
            f"Turnover about {_num(portfolio['turnover_annual'])}x NAV per year "
            "(one-way traded notional / average NAV). "
            f"{portfolio['trade_count']} fills. Terminal cash weight {_pct(portfolio['terminal_cash_weight'])}. "
            f"Regime sessions: {portfolio['regime_sessions']}."
        ),
        "",
        f"Fills by name: {count_line}.",
        "",
        _window_block("Full sample", portfolio["full"]),
        "",
        _window_block("In sample", portfolio["in_sample"]),
        "",
        _window_block("Out of sample", portfolio["out_of_sample"]),
        "",
        _window_block("Before Ondo (proxy)", portfolio["pre_ondo"]),
        "",
        _window_block("From Ondo live date", portfolio["post_ondo"]),
        "",
        "## Crypto derivatives",
        "",
        derivatives["pricing_note"],
        "",
        f"Full sample: {_summary_line(derivatives['full'])}.",
        "",
        f"In sample: {_summary_line(derivatives['in_sample'])}.",
        "",
        f"Out of sample: {_summary_line(derivatives['out_of_sample'])}.",
        "",
        _deriv_table(derivatives["rows"]),
        "",
        "## Current book snapshot",
        "",
        f"As of {book.get('as_of', 'n/a')}, about ${book.get('nav_usd', 'n/a')}: {weight_line}.",
        "",
        str(book.get("note") or ""),
        "",
        f"Trade-log comparison (plus or minus 5 days): {compared}.",
        "",
        "## Assumptions and limits",
        "",
    ]
    lines.extend(f"- {item}" for item in ASSUMPTIONS)
    lines.extend([
        "",
        "## Data",
        "",
        f"Panel series: {meta.get('series_count', 'n/a')}. Sources: {meta.get('sources', {})}.",
        "",
        portfolio["proxy_note"],
        "",
    ])
    return "\n".join(lines)
