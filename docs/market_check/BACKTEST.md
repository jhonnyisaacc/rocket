# Market-check backtest

Window 2024-10-01 to 2026-09-30 (501 equity sessions). Out-of-sample starts 2025-10-01. Ondo proxy before 2025-09-02.

This is a research record of one rule set on one history. It is not a forecast and not an instruction to trade.

## Portfolio

Turnover about 0.61x NAV per year (one-way traded notional / average NAV). 184 fills. Terminal cash weight 43.9%. Regime sessions: {'risk-on': 395, 'neutral': 105, 'risk-off': 1}.

Fills by name: AMAT 11 buys/0 sells, AMZN 1 buys/23 sells, BAC 1 buys/5 sells, CAT 1 buys/0 sells, EQIX 1 buys/37 sells, ETN 3 buys/0 sells, FCX 1 buys/8 sells, META 1 buys/48 sells, MSFT 1 buys/26 sells, TSLA 1 buys/15 sells.

### Full sample

- Strategy: 27.2% CAGR, -24.5% max DD, 23.3% vol, 0.98 Sharpe, 61.7% total
- Equal-weight buy-and-hold: 28.3% CAGR, -28.3% max DD, 26.9% vol, 1.07 Sharpe, 64.4% total
- SPY: 17.2% CAGR, -18.8% max DD, 16.5% vol, 1.05 Sharpe, 37.2% total
- QQQ (extra): 24.7% CAGR, -22.8% max DD, 21.8% vol, 1.13 Sharpe, 55.3% total

| Month | Strategy | Equal-weight | SPY |
|---|---:|---:|---:|
| 2024-10 | -0.7% | -1.2% | 0.0% |
| 2024-11 | 6.3% | 9.4% | 6.0% |
| 2024-12 | 0.2% | -2.5% | -2.4% |
| 2025-01 | 2.0% | 3.2% | 2.7% |
| 2025-02 | -4.3% | -8.2% | -1.3% |
| 2025-03 | -5.5% | -7.5% | -5.6% |
| 2025-04 | 1.5% | 2.5% | -0.9% |
| 2025-05 | 4.3% | 12.5% | 6.3% |
| 2025-06 | 5.3% | 6.7% | 5.1% |
| 2025-07 | 1.6% | 3.5% | 2.3% |
| 2025-08 | -3.9% | -0.7% | 2.1% |
| 2025-09 | 6.7% | 7.9% | 3.6% |
| 2025-10 | 5.8% | 6.4% | 2.4% |
| 2025-11 | 0.5% | -1.9% | 0.2% |
| 2025-12 | -0.1% | 0.9% | 0.1% |
| 2026-01 | 8.9% | 6.5% | 1.5% |
| 2026-02 | 5.4% | 2.4% | -0.9% |
| 2026-03 | -3.7% | -7.1% | -4.9% |
| 2026-04 | 9.2% | 13.8% | 10.5% |
| 2026-05 | 5.2% | 3.9% | 5.3% |
| 2026-06 | 27.2% | 11.1% | -1.0% |
| 2026-07 | -17.2% | -10.1% | 0.0% |
| 2026-08 | -4.7% | 1.3% | 2.7% |
| 2026-09 | 5.5% | 2.2% | -0.3% |

### In sample

- Strategy: 13.2% CAGR, -16.6% max DD, 15.8% vol, 0.59 Sharpe, 13.2% total
- Equal-weight buy-and-hold: 26.2% CAGR, -28.3% max DD, 27.3% vol, 1.00 Sharpe, 26.1% total
- SPY: 18.7% CAGR, -18.8% max DD, 19.5% vol, 0.98 Sharpe, 18.6% total
- QQQ (extra): 25.5% CAGR, -22.8% max DD, 23.5% vol, 1.09 Sharpe, 25.4% total

| Month | Strategy | Equal-weight | SPY |
|---|---:|---:|---:|
| 2024-10 | -0.7% | -1.2% | 0.0% |
| 2024-11 | 6.3% | 9.4% | 6.0% |
| 2024-12 | 0.2% | -2.5% | -2.4% |
| 2025-01 | 2.0% | 3.2% | 2.7% |
| 2025-02 | -4.3% | -8.2% | -1.3% |
| 2025-03 | -5.5% | -7.5% | -5.6% |
| 2025-04 | 1.5% | 2.5% | -0.9% |
| 2025-05 | 4.3% | 12.5% | 6.3% |
| 2025-06 | 5.3% | 6.7% | 5.1% |
| 2025-07 | 1.6% | 3.5% | 2.3% |
| 2025-08 | -3.9% | -0.7% | 2.1% |
| 2025-09 | 6.7% | 7.9% | 3.6% |

### Out of sample

- Strategy: 42.9% CAGR, -24.5% max DD, 28.8% vol, 1.26 Sharpe, 42.9% total
- Equal-weight buy-and-hold: 30.4% CAGR, -16.8% max DD, 26.5% vol, 1.14 Sharpe, 30.3% total
- SPY: 15.7% CAGR, -8.9% max DD, 13.0% vol, 1.19 Sharpe, 15.7% total
- QQQ (extra): 23.8% CAGR, -12.0% max DD, 20.0% vol, 1.17 Sharpe, 23.8% total

| Month | Strategy | Equal-weight | SPY |
|---|---:|---:|---:|
| 2025-09 | 0.0% | 0.0% | 0.0% |
| 2025-10 | 5.8% | 6.4% | 2.4% |
| 2025-11 | 0.5% | -1.9% | 0.2% |
| 2025-12 | -0.1% | 0.9% | 0.1% |
| 2026-01 | 8.9% | 6.5% | 1.5% |
| 2026-02 | 5.4% | 2.4% | -0.9% |
| 2026-03 | -3.7% | -7.1% | -4.9% |
| 2026-04 | 9.2% | 13.8% | 10.5% |
| 2026-05 | 5.2% | 3.9% | 5.3% |
| 2026-06 | 27.2% | 11.1% | -1.0% |
| 2026-07 | -17.2% | -10.1% | 0.0% |
| 2026-08 | -4.7% | 1.3% | 2.7% |
| 2026-09 | 5.5% | 2.2% | -0.3% |

### Before Ondo (proxy)

- Strategy: 6.7% CAGR, -16.6% max DD, 16.2% vol, 0.21 Sharpe, 6.1% total
- Equal-weight buy-and-hold: 18.8% CAGR, -28.3% max DD, 28.2% vol, 0.75 Sharpe, 16.9% total
- SPY: 16.1% CAGR, -18.8% max DD, 20.3% vol, 0.84 Sharpe, 14.5% total
- QQQ (extra): 21.1% CAGR, -22.8% max DD, 24.4% vol, 0.91 Sharpe, 19.0% total

| Month | Strategy | Equal-weight | SPY |
|---|---:|---:|---:|
| 2024-10 | -0.7% | -1.2% | 0.0% |
| 2024-11 | 6.3% | 9.4% | 6.0% |
| 2024-12 | 0.2% | -2.5% | -2.4% |
| 2025-01 | 2.0% | 3.2% | 2.7% |
| 2025-02 | -4.3% | -8.2% | -1.3% |
| 2025-03 | -5.5% | -7.5% | -5.6% |
| 2025-04 | 1.5% | 2.5% | -0.9% |
| 2025-05 | 4.3% | 12.5% | 6.3% |
| 2025-06 | 5.3% | 6.7% | 5.1% |
| 2025-07 | 1.6% | 3.5% | 2.3% |
| 2025-08 | -3.9% | -0.7% | 2.1% |

### From Ondo live date

- Strategy: 47.4% CAGR, -24.5% max DD, 27.9% vol, 1.41 Sharpe, 52.5% total
- Equal-weight buy-and-hold: 36.8% CAGR, -16.8% max DD, 25.7% vol, 1.36 Sharpe, 40.6% total
- SPY: 18.1% CAGR, -8.9% max DD, 12.6% vol, 1.39 Sharpe, 19.8% total
- QQQ (extra): 27.7% CAGR, -12.0% max DD, 19.3% vol, 1.37 Sharpe, 30.5% total

| Month | Strategy | Equal-weight | SPY |
|---|---:|---:|---:|
| 2025-08 | 0.0% | 0.0% | 0.0% |
| 2025-09 | 6.7% | 7.9% | 3.6% |
| 2025-10 | 5.8% | 6.4% | 2.4% |
| 2025-11 | 0.5% | -1.9% | 0.2% |
| 2025-12 | -0.1% | 0.9% | 0.1% |
| 2026-01 | 8.9% | 6.5% | 1.5% |
| 2026-02 | 5.4% | 2.4% | -0.9% |
| 2026-03 | -3.7% | -7.1% | -4.9% |
| 2026-04 | 9.2% | 13.8% | 10.5% |
| 2026-05 | 5.2% | 3.9% | 5.3% |
| 2026-06 | 27.2% | 11.1% | -1.0% |
| 2026-07 | -17.2% | -10.1% | 0.0% |
| 2026-08 | -4.7% | 1.3% | 2.7% |
| 2026-09 | 5.5% | 2.2% | -0.3% |

## Crypto derivatives

Perps are spot plus historical funding, with fees and slippage. Puts are Black-Scholes, marked with that day's Deribit DVOL when it exists, otherwise with trailing realized volatility. They are not Deribit trade prints. DVOL is a 30-day index used on a 60-day put. Each month is a fresh 1-BTC notional; the sum of monthly P&L is the primary total, not a compounded equity curve.

Full sample: hit rate 41.2% on 17 active months, sum of monthly P&L 13.2%, worst -9.5%, best 37.0%, perp hit rate 45.5%, put hit rate 36.4%, stops 4.

In sample: hit rate 55.6% on 9 active months, sum of monthly P&L 21.0%, worst -9.5%, best 37.0%, perp hit rate 55.6%, put hit rate 0.0%, stops 2.

Out of sample: hit rate 25.0% on 8 active months, sum of monthly P&L -7.7%, worst -7.3%, best 4.7%, perp hit rate 0.0%, put hit rate 50.0%, stops 2.

| Month | Signal | Position | Entry | Exit | P&L | Success |
|---|---|---|---:|---:|---:|---|
| 2024-10 | risk-on / flat | flat 0  | 60837 | 70215 | 0.00% | n/a |
| 2024-11 | risk-on / long 1 | long 1  | 69482 | 96449 | 37.04% | yes |
| 2024-12 | risk-on / long 1 | long 1  | 97280 | 93429 | -5.14% | no |
| 2025-01 | risk-on / long 0.5 | long 0.5  | 94420 | 102405 | 3.53% | yes |
| 2025-02 | risk-on / long 1 | long 1  | 100656 | 91418 | -9.52% | no |
| 2025-03 | risk-on / long 0.5 | long 0.5  | 86032 | 78532 | -4.40% | no |
| 2025-04 | neutral / flat | flat 0  | 85169 | 94207 | 0.00% | n/a |
| 2025-05 | neutral / flat | flat 0  | 96492 | 104638 | 0.00% | n/a |
| 2025-06 | risk-on / long 1 | long 1  | 105652 | 107135 | 1.15% | yes |
| 2025-07 | risk-on / long 0.5 | long 0.5 +put | 105698 | 115758 | 3.22% | yes |
| 2025-08 | risk-on / long 1 | long 1 +put | 113320 | 108237 | -5.68% | no |
| 2025-09 | risk-on / long 0.5 | long 0.5 +put | 109251 | 114056 | 0.79% | yes |
| 2025-10 | risk-on / long 1 | long 1 +put | 118649 | 108186 | -7.32% | no |
| 2025-11 | risk-on / long 0.5 | long 0.5 +put | 110064 | 99697 | -2.99% | no |
| 2025-12 | risk-on / flat | flat 0  | 86322 | 87509 | 0.00% | n/a |
| 2026-01 | risk-on / flat | flat 0 +put | 88732 | 78621 | 1.58% | yes |
| 2026-02 | neutral / flat | flat 0  | 76974 | 66996 | 0.00% | n/a |
| 2026-03 | risk-on / flat | flat 0  | 65738 | 68233 | 0.00% | n/a |
| 2026-04 | neutral / flat | flat 0  | 68079 | 76304 | 0.00% | n/a |
| 2026-05 | risk-on / flat | flat 0 +put | 78179 | 73580 | -0.36% | no |
| 2026-06 | risk-on / flat | flat 0 +put | 71320 | 58559 | 4.73% | yes |
| 2026-07 | risk-on / flat | flat 0 +put | 60004 | 62814 | -1.45% | no |
| 2026-08 | neutral / flat | flat 0 +put | 62763 | 78549 | -0.89% | no |
| 2026-09 | neutral / flat | flat 0 +put | 77404 | 83554 | -1.05% | no |

## Current book snapshot

As of 2026-09-30, about $798.0: MSFT 15.6%, META 15.5%, FCX 14.4%, BAC 13.1%, AMZN 12.9%, EQIX 12.5%, USDC 15.6%.

Snapshot only. No cost basis exists before 2026-09-15, so the backtest does not replay this book.

Trade-log comparison (plus or minus 5 days): 2026-09-23 sell TSLA not matched.

## Assumptions and limits

- Read-only research. Nothing here is an order, a target weight to send to a venue, or a claim of a tradable edge.
- Same-close fills. The decision for session T can use the session T close, and the fill is that close plus slippage. Stops are daily-close stops; a wick through the stop is invisible.
- No look-ahead. Every read goes through an as-of view. Credit OAS and effective fed funds are lagged one calendar day. Treasury yields, equities, VIX, oil, the dollar, gold, bitcoin, DVOL and funding use the same close. That is slightly generous for yields that print in the afternoon.
- MOVE is not on a free historical feed. The volatility pillar uses VIX plus the 20-session annualized realized volatility of TLT, and the thresholds are in TLT-vol units.
- Credit prefers FRED BAMLH0A0HYM2 (and IG OAS when it is present). If the OAS series is missing, the 20-session HYG/LQD return is the fallback and is labeled as such.
- The dollar series is ICE DXY when Yahoo has it, otherwise the broad trade-weighted dollar. Oil is FRED spot when the download succeeds, otherwise the front-month future.
- BTC options are Black-Scholes. Implied vol is Deribit DVOL when that day's print exists, otherwise trailing realized vol. These are not historical Deribit trade prices. DVOL is a 30-day index applied to a 60-day, 15 percent out-of-the-money put. Entry IV is worsened by the configured slippage.
- Perp funding is the sum of Deribit BTC-PERPETUAL hourly interest_1h, in fraction of notional. Positive funding is paid by longs. A short does not also buy puts unless put_with_short is turned on.
- The equity book is long-only and unlevered. USDC earns nothing in the simulation. Prices are split- and dividend-adjusted closes, so dividends are in the path rather than paid as cash. Ondo tokenized stocks are the underlying one-for-one. Sessions before the configured Ondo date are a proxy and are reported as their own window. Equity slippage is charged on every fill, including the opening buys of the strategy and the benchmarks.
- Porto rules. Cash target is 35, 40 or 45 percent in risk-on, neutral and risk-off. An up day in the index raises the target by one step, capped at 45 percent. Adds are only ETN, CAT, APH and AMAT, only in the bottom half of the trailing buy zone, and never in risk-off, on an FOMC decision date, or on an oil-shock day. Trims follow TSLA, FCX, BAC, then half of META, EQIX and MSFT, then a light AMZN trim. A name that is down on the day is not sold. Nothing is sold on a hard-down index day. Two of the three trim gates must pass; on daily bars the regular-hours gate always passes. There is no daily rebalance back to equal weight.
- The regime can block adds and move the cash target. It does not authorize selling into a red name or a hard-down day.
- Parameters live in config/market_check.toml. They were set from the stated rules and from round level thresholds, and they were not searched against this result. The out-of-sample split is the second half of the window, same parameters.
- Phillip's private numeric bands are not in the repo. The daily check uses the bottom quartile of the trailing range and shifts it with the regime. That is a stand-in.
- The September 2026 book snapshot is printed for context. There is no cost basis before 15 September 2026, so the backtest does not replay that book. An optional trade-log CSV is only a comparison.
- One path, one parameter set, and real approximation error on options, funding and same-close fills. A better in-sample number would not, by itself, be evidence to size up.

## Data

Panel series: 36. Sources: {'AMAT': 'Yahoo Finance AMAT adjusted close', 'AMZN': 'Yahoo Finance AMZN adjusted close', 'APH': 'Yahoo Finance APH adjusted close', 'BAC': 'Yahoo Finance BAC adjusted close', 'BE': 'Yahoo Finance BE adjusted close', 'CAT': 'Yahoo Finance CAT adjusted close', 'CRWD': 'Yahoo Finance CRWD adjusted close', 'DDOG': 'Yahoo Finance DDOG adjusted close', 'EQIX': 'Yahoo Finance EQIX adjusted close', 'ETN': 'Yahoo Finance ETN adjusted close', 'FCX': 'Yahoo Finance FCX adjusted close', 'META': 'Yahoo Finance META adjusted close', 'MRVL': 'Yahoo Finance MRVL adjusted close', 'MSFT': 'Yahoo Finance MSFT adjusted close', 'SPCX': 'Yahoo Finance SPCX adjusted close', 'TSLA': 'Yahoo Finance TSLA adjusted close', 'VST': 'Yahoo Finance VST adjusted close', 'brent': 'FRED DCOILBRENTEU', 'btc': 'Yahoo Finance BTC-USD adjusted close', 'dollar': 'Yahoo Finance DX-Y.NYB adjusted close', 'dvol': 'Deribit BTC DVOL daily close', 'fed_funds': 'New York Fed EFFR', 'funding_daily': 'Deribit BTC-PERPETUAL sum of hourly interest_1h', 'gold': 'Yahoo Finance GC=F adjusted close', 'hy_oas': 'FRED BAMLH0A0HYM2', 'hyg': 'Yahoo Finance HYG adjusted close', 'ig_oas': 'FRED BAMLC0A0CM', 'lqd': 'Yahoo Finance LQD adjusted close', 'qqq': 'Yahoo Finance QQQ adjusted close', 'spy': 'Yahoo Finance SPY adjusted close', 'tlt': 'Yahoo Finance TLT adjusted close', 'vix': 'FRED VIXCLS', 'wti': 'FRED DCOILWTICO', 'yield_10y': 'US Treasury daily par yield curve', 'yield_2y': 'US Treasury daily par yield curve', 'yield_30y': 'US Treasury daily par yield curve'}.

Sessions before the Ondo live date are marked as a 1:1 underlying proxy. The same slippage is charged the whole way; the split is reported separately.
