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
    "Porto rules. Cash target is 35, 40, 42 or 45 percent in risk-on, neutral, caution and risk-off. An up day in the index raises the target by one step, capped at 45 percent. Adds are only ETN, CAT, APH and AMAT, only in the bottom half of the trailing buy zone, and never in caution or risk-off, on an FOMC decision date, or on an oil-shock day. Trims follow TSLA, FCX, BAC, then half of META, EQIX and MSFT, then a light AMZN trim. A name that is down on the day is not sold. Nothing is sold on a hard-down index day. Two of the three trim gates must pass; on daily bars the regular-hours gate always passes. There is no daily rebalance back to equal weight.",
    "The regime can block adds and move the cash target. Caution is the middle tier: higher cash, no new adds, a flat perp. It does not authorize selling into a red name or a hard-down day, and it does not by itself short BTC.",
    "Risk-off is a stress score with hysteresis, not a pillar-level rule. Points come from a VIX jump, credit-spread widening, a 30-year yield breakout, an oil shock, and a BTC drawdown. Enter risk-off at 4, leave it below 2; enter caution at 2, leave it below 1. Red rates plus red volatility or red credit is only an entry backstop. v3 leaves that caution when VIX falls off a spike of 25 or more while SPY is still 12% under its 60-session high, then buys up to three tranches and does not trim while the release is on. The release ends once the stress score cools below the caution exit, so the next rise can raise cash again. The 12% gate is the in-sample distinction between the failed March 2025 fade and the April low. It was not lowered to catch a later, smaller dip.",
    "v4 raises cash to the risk-off target only when VIX is at or above 25 and high-yield credit has widened by at least 40bp over 20 sessions. Other stress either stays in the 35-45% band or, if that lost in sample, uses a 27.5% caution with adds paused. Redeployed shares are held until the next caution or risk-off after a quiet day, so quiet up-days do not refill cash. BTC longs use the same hold. Puts are included only when they raised in-sample P&L. The choice uses the in-sample half and is not refit out of sample.",
    "Parameters otherwise live in config/market_check.toml. The out-of-sample split is the second half of the window, same parameters.",
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
        f"perp P&L {_pct(stats.get('perp_pnl'))}, "
        f"put P&L {_pct(stats.get('put_pnl'))}, "
        f"stops {stats.get('stopped')}"
    )


def _trade_status(row: dict[str, Any]) -> str:
    label = f"{row['date']} {row['side']} {row['ticker']}"
    if row.get("status") == "matched" or row.get("matched"):
        return f"{label} matched {','.join(row.get('simulated_dates') or [])}"
    if row.get("status") == "already_exited":
        return (
            f"{label} recognized as already exited on {row.get('last_simulated')} "
            f"({row.get('days_apart')} days earlier). {row.get('explanation') or ''}"
        )
    return f"{label} not matched. {row.get('explanation') or ''}"


def _when(value: int | None, *, versus: str) -> str:
    if value is None:
        return "none"
    if versus == "peak":
        if value < 0:
            return f"{-value}d before peak"
        if value > 0:
            return f"{value}d after peak"
        return "on the peak"
    if value > 0:
        return f"{value}d before the low"
    if value < 0:
        return f"{-value}d after the low"
    return "on the low"


def _count_line(counts: dict[str, int] | None) -> str:
    if not counts:
        return "none"
    order = ("risk-off", "caution", "neutral", "risk-on", "unknown")
    parts = [f"{name} {counts[name]}" for name in order if counts.get(name)]
    extra = [f"{name} {value}" for name, value in sorted(counts.items()) if name not in order and value]
    return ", ".join([*parts, *extra]) or "none"


def _stress_section(record: dict[str, Any]) -> str:
    sessions = record.get("sessions") or {}
    lines = [
        "## Risk-off and caution",
        "",
        str(record.get("note") or ""),
        "",
        (
            f"In-sample sessions: {_count_line(sessions.get('in_sample'))}. "
            f"Out-of-sample sessions: {_count_line(sessions.get('out_of_sample'))}. "
            "A day count versus the peak is a lead when the warning is earlier. "
            "Days versus the low are how early the warning sat before the trough."
        ),
        "",
        "| Regime | Start | End | Sessions | Sample |",
        "|---|---|---|---:|---|",
    ]
    episodes = record.get("episodes") or []
    if not episodes:
        lines.append("| none | | | | |")
    for row in episodes:
        lines.append(
            f"| {row['regime']} | {row['start']} | {row['end']} | {row['sessions']} | {row['sample']} |"
        )
    lines.extend([
        "",
        (
            "Large drawdowns are a peak-to-trough of at least 8% in SPY or 15% in BTC. "
            "The search window starts 10 equity sessions before the peak and ends at the trough."
        ),
        "",
        "| Asset | Sample | Peak | Trough | Depth | Caution | Risk-off | Caution vs peak | Risk-off vs peak | Caution vs low | Risk-off vs low |",
        "|---|---|---|---|---:|---|---|---|---|---|---|",
    ])
    drawdowns = record.get("drawdowns") or []
    if not drawdowns:
        lines.append("| none | | | | | | | | | | |")
    for row in drawdowns:
        lines.append(
            "| {asset} | {sample} | {peak} | {trough} | {depth} | {caution} | {risk} | {cpeak} | {rpeak} | {clow} | {rlow} |".format(
                asset=row["asset"],
                sample=row["sample"],
                peak=row["peak"],
                trough=row["trough"],
                depth=_pct(row["depth"]),
                caution=row.get("first_caution") or "none",
                risk=row.get("first_risk_off") or "none",
                cpeak=_when(row.get("caution_vs_peak_days"), versus="peak"),
                rpeak=_when(row.get("risk_off_vs_peak_days"), versus="peak"),
                clow=_when(row.get("caution_vs_trough_days"), versus="low"),
                rlow=_when(row.get("risk_off_vs_trough_days"), versus="low"),
            )
        )
    return "\n".join(lines)


def _stat(block: dict[str, Any] | None, key: str) -> str:
    stats = (block or {}).get(key) or {}
    sharpe = stats.get("sharpe")
    sharpe_text = "n/a" if not isinstance(sharpe, (int, float)) else f"{sharpe:.2f}"
    return f"{_pct(stats.get('cagr'))} / {_pct(stats.get('max_drawdown'))} / {sharpe_text}"


def _entry_rows(entries: list[dict[str, Any]], sample: str, asset: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for row in entries:
        if sample != "full" and row["sample"] != sample:
            continue
        if row.get("avg_entry_vs_low") is None:
            continue
        if asset is None and row["asset"] in {"SPY", "BTC"}:
            continue
        if asset is not None and row["asset"] != asset:
            continue
        rows.append(row)
    return rows


def _entry_line(entries: list[dict[str, Any]], sample: str, asset: str | None = None) -> str:
    rows = _entry_rows(entries, sample, asset)
    if not rows:
        return "no buys near the lows"
    average = sum(float(row["avg_entry_vs_low"]) for row in rows) / len(rows)
    noun = "drawdown" if len(rows) == 1 else "drawdowns"
    return f"{average:.1%} above the trough across {len(rows)} {noun}"


def _comparison_section(comparison: dict[str, Any], selection: dict[str, Any]) -> str:
    lines = [
        "## Four versions",
        "",
        (
            "v1 is the original level rule (risk-off almost never fired). "
            "v2 is the stress score with hysteresis and caution, which raised cash and did not redeploy it. "
            "v3 keeps that stress score and adds the buy-the-low release: three tranches into the "
            "quality name and the high-beta name that fell most and have started to bounce, "
            "and BTC longs only on that signal with puts only on a fresh warning. "
            "v4 holds those shares until the next warning, and raises cash only on VIX at or above 25 "
            "plus a 40bp credit widening. "
            "CAGR / max drawdown / Sharpe. Benchmarks are the same in every version. "
            "Perp P&L and put P&L are separate; the hit rate is the combined month."
        ),
        "",
        _selection_note(selection),
        "",
        "| Version | Sample | Strategy | Equal-weight | SPY | Hit | Perp P&L | Put P&L | Stock entries vs low | BTC entry vs low |",
        "|---|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for version in ("v1", "v2", "v3", "v4"):
        block = comparison.get(version) or {}
        derivs = block.get("derivatives") or {}
        entries = block.get("entries") or []
        for sample, label in (
            ("full", "full"),
            ("in_sample", "in sample"),
            ("out_of_sample", "out of sample"),
        ):
            stats = derivs.get("full" if sample == "full" else sample) or {}
            lines.append(
                "| {version} | {label} | {strategy} | {bench} | {spy} | {hit} | {perp} | {put} | {stocks} | {btc} |".format(
                    version=version,
                    label=label,
                    strategy=_stat(block.get(sample), "strategy"),
                    bench=_stat(block.get(sample), "equal_weight"),
                    spy=_stat(block.get(sample), "spy"),
                    hit=_pct(stats.get("hit_rate")),
                    perp=_pct(stats.get("perp_pnl")),
                    put=_pct(stats.get("put_pnl")),
                    stocks=_entry_line(entries, sample),
                    btc=_entry_line(entries, sample, "BTC"),
                )
            )
    lines.append("")
    lines.append(
        "Entry versus low is the average fill divided by the price on the trough day, minus one. "
        "Zero would be buying the low. Stock rows use buys from the peak through three weeks after "
        "the trough. BTC uses the long opened by that version, if any."
    )
    lines.append("")
    return "\n".join(lines)


def _selection_note(selection: dict[str, Any]) -> str:
    if not selection:
        return "v4's in-sample horse race was not attached to this result."
    caution = selection.get("caution")
    puts = selection.get("puts")
    band = (
        f"Normal 35-45% band: in-sample CAGR {_pct(selection.get('band_cagr'))}, "
        f"max DD {_pct(selection.get('band_dd'))}, Sharpe {_num(selection.get('band_sharpe'))}."
    )
    light = (
        f"Lighter 27.5% caution with adds paused: in-sample CAGR {_pct(selection.get('light_cagr'))}, "
        f"max DD {_pct(selection.get('light_dd'))}, Sharpe {_num(selection.get('light_sharpe'))}."
    )
    chosen = "the normal band" if caution == "band" else "the lighter caution"
    put_line = (
        f"Warning puts, in sample, summed to {_pct(selection.get('puts_pnl'))} with the long "
        f"and {_pct(selection.get('no_puts_pnl'))} without them "
        f"(put sleeve {_pct(selection.get('puts_only'))}, long sleeve {_pct(selection.get('long_pnl'))}). "
    )
    put_choice = "Puts stay in." if puts else "Puts are dropped."
    return (
        f"{band} {light} The higher in-sample Sharpe is {chosen}; a tie would keep the band. "
        f"{put_line}{put_choice} A tie would drop them. Out-of-sample results were not used for either choice."
    )


def _oos_verdict(comparison: dict[str, Any]) -> str:
    bench = None
    winners = []
    lines = []
    for version in ("v1", "v2", "v3", "v4"):
        block = ((comparison.get(version) or {}).get("out_of_sample") or {})
        strategy = block.get("strategy") or {}
        equal = block.get("equal_weight") or {}
        sharpe = strategy.get("sharpe")
        bench = equal.get("sharpe") if bench is None else bench
        if isinstance(sharpe, (int, float)) and isinstance(bench, (int, float)) and sharpe > bench:
            winners.append(version)
        lines.append(f"{version} Sharpe {_num(sharpe)}")
    detail = ", ".join(lines)
    if not isinstance(bench, (int, float)):
        return "Out-of-sample Sharpe could not be compared with equal-weight."
    if not winners:
        return (
            f"Out of sample, none of v1, v2, v3, or v4 beats equal-weight buy-and-hold on Sharpe "
            f"({_num(bench)}). {detail}."
        )
    names = ", ".join(winners)
    return (
        f"Out of sample, {names} beat equal-weight buy-and-hold on Sharpe ({_num(bench)}). "
        f"{detail}. That is one path, and a higher Sharpe with a deeper drawdown is still one path."
    )


def _next_section(comparison: dict[str, Any]) -> str:
    lines = [
        "## What to improve next",
        "",
        _oos_verdict(comparison),
        "",
        (
            "Credit tightening lagged the in-sample low by weeks, so it stays a confirmation rather than an entry. "
            "Funding turning negative marked the middle of the BTC decline, not the turn. "
            "The panel has no volume, so a capitulation-volume rule is untested. "
            "The 12% drawdown gate was set because the shallower March 2025 fade failed in sample. "
            "A rule aimed at later, smaller dips would be a new claim, not a tweak of this one. "
            "Puts are still Black-Scholes on a 30-day DVOL, and same-close fills remain."
        ),
        "",
    ]
    return "\n".join(lines)


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
        compared = "; ".join(_trade_status(row) for row in comparison)
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
        _stress_section(result.get("stress_record") or {}),
        "",
        _comparison_section(result.get("comparison") or {}, result.get("v4_selection") or {}),
        "",
        (result.get("diagnosis") or {}).get("markdown") or "",
        "",
        _next_section(result.get("comparison") or {}),
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
        f"Trade-log comparison (plus or minus 5 days): {compared}",
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
