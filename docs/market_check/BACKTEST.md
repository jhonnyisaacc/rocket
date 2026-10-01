# Market-check backtest

Window 2024-10-01 to 2026-09-30 (501 equity sessions). Out-of-sample starts 2025-10-01. Ondo proxy before 2025-09-02.

This is a research record of one rule set on one history. It is not a forecast and not an instruction to trade.

## Portfolio

Turnover about 0.57x NAV per year (one-way traded notional / average NAV). 60 fills. Terminal cash weight 46.9%. Regime sessions: {'risk-on': 240, 'caution': 170, 'risk-off': 45, 'neutral': 46}.

Fills by name: AMAT 4 buys/0 sells, AMZN 1 buys/0 sells, BAC 2 buys/19 sells, EQIX 1 buys/1 sells, ETN 1 buys/0 sells, FCX 1 buys/4 sells, META 3 buys/8 sells, MSFT 1 buys/0 sells, TSLA 3 buys/11 sells.

### Full sample

- Strategy: 14.4% CAGR, -15.5% max DD, 14.5% vol, 0.73 Sharpe, 30.8% total
- Equal-weight buy-and-hold: 28.3% CAGR, -28.3% max DD, 26.9% vol, 1.07 Sharpe, 64.4% total
- SPY: 17.2% CAGR, -18.8% max DD, 16.5% vol, 1.05 Sharpe, 37.2% total
- QQQ (extra): 24.7% CAGR, -22.8% max DD, 21.8% vol, 1.13 Sharpe, 55.3% total

| Month | Strategy | Equal-weight | SPY |
|---|---:|---:|---:|
| 2024-10 | -0.7% | -1.2% | 0.0% |
| 2024-11 | 5.1% | 9.4% | 6.0% |
| 2024-12 | -0.4% | -2.5% | -2.4% |
| 2025-01 | 1.9% | 3.2% | 2.7% |
| 2025-02 | -3.5% | -8.2% | -1.3% |
| 2025-03 | -5.3% | -7.5% | -5.6% |
| 2025-04 | 1.3% | 2.5% | -0.9% |
| 2025-05 | 7.1% | 12.5% | 6.3% |
| 2025-06 | 4.3% | 6.7% | 5.1% |
| 2025-07 | 1.9% | 3.5% | 2.3% |
| 2025-08 | -1.8% | -0.7% | 2.1% |
| 2025-09 | 2.1% | 7.9% | 3.6% |
| 2025-10 | 1.5% | 6.4% | 2.4% |
| 2025-11 | -0.9% | -1.9% | 0.2% |
| 2025-12 | 0.3% | 0.9% | 0.1% |
| 2026-01 | 3.7% | 6.5% | 1.5% |
| 2026-02 | 0.4% | 2.4% | -0.9% |
| 2026-03 | -3.1% | -7.1% | -4.9% |
| 2026-04 | 7.8% | 13.8% | 10.5% |
| 2026-05 | 3.2% | 3.9% | 5.3% |
| 2026-06 | 7.8% | 11.1% | -1.0% |
| 2026-07 | -5.7% | -10.1% | 0.0% |
| 2026-08 | -1.3% | 1.3% | 2.7% |
| 2026-09 | 3.2% | 2.2% | -0.3% |

### In sample

- Strategy: 11.7% CAGR, -15.5% max DD, 14.0% vol, 0.55 Sharpe, 11.7% total
- Equal-weight buy-and-hold: 26.2% CAGR, -28.3% max DD, 27.3% vol, 1.00 Sharpe, 26.1% total
- SPY: 18.7% CAGR, -18.8% max DD, 19.5% vol, 0.98 Sharpe, 18.6% total
- QQQ (extra): 25.5% CAGR, -22.8% max DD, 23.5% vol, 1.09 Sharpe, 25.4% total

| Month | Strategy | Equal-weight | SPY |
|---|---:|---:|---:|
| 2024-10 | -0.7% | -1.2% | 0.0% |
| 2024-11 | 5.1% | 9.4% | 6.0% |
| 2024-12 | -0.4% | -2.5% | -2.4% |
| 2025-01 | 1.9% | 3.2% | 2.7% |
| 2025-02 | -3.5% | -8.2% | -1.3% |
| 2025-03 | -5.3% | -7.5% | -5.6% |
| 2025-04 | 1.3% | 2.5% | -0.9% |
| 2025-05 | 7.1% | 12.5% | 6.3% |
| 2025-06 | 4.3% | 6.7% | 5.1% |
| 2025-07 | 1.9% | 3.5% | 2.3% |
| 2025-08 | -1.8% | -0.7% | 2.1% |
| 2025-09 | 2.1% | 7.9% | 3.6% |

### Out of sample

- Strategy: 17.1% CAGR, -11.1% max DD, 14.9% vol, 0.89 Sharpe, 17.1% total
- Equal-weight buy-and-hold: 30.4% CAGR, -16.8% max DD, 26.5% vol, 1.14 Sharpe, 30.3% total
- SPY: 15.7% CAGR, -8.9% max DD, 13.0% vol, 1.19 Sharpe, 15.7% total
- QQQ (extra): 23.8% CAGR, -12.0% max DD, 20.0% vol, 1.17 Sharpe, 23.8% total

| Month | Strategy | Equal-weight | SPY |
|---|---:|---:|---:|
| 2025-09 | 0.0% | 0.0% | 0.0% |
| 2025-10 | 1.5% | 6.4% | 2.4% |
| 2025-11 | -0.9% | -1.9% | 0.2% |
| 2025-12 | 0.3% | 0.9% | 0.1% |
| 2026-01 | 3.7% | 6.5% | 1.5% |
| 2026-02 | 0.4% | 2.4% | -0.9% |
| 2026-03 | -3.1% | -7.1% | -4.9% |
| 2026-04 | 7.8% | 13.8% | 10.5% |
| 2026-05 | 3.2% | 3.9% | 5.3% |
| 2026-06 | 7.8% | 11.1% | -1.0% |
| 2026-07 | -5.7% | -10.1% | 0.0% |
| 2026-08 | -1.3% | 1.3% | 2.7% |
| 2026-09 | 3.2% | 2.2% | -0.3% |

### Before Ondo (proxy)

- Strategy: 10.4% CAGR, -15.5% max DD, 14.5% vol, 0.45 Sharpe, 9.4% total
- Equal-weight buy-and-hold: 18.8% CAGR, -28.3% max DD, 28.2% vol, 0.75 Sharpe, 16.9% total
- SPY: 16.1% CAGR, -18.8% max DD, 20.3% vol, 0.84 Sharpe, 14.5% total
- QQQ (extra): 21.1% CAGR, -22.8% max DD, 24.4% vol, 0.91 Sharpe, 19.0% total

| Month | Strategy | Equal-weight | SPY |
|---|---:|---:|---:|
| 2024-10 | -0.7% | -1.2% | 0.0% |
| 2024-11 | 5.1% | 9.4% | 6.0% |
| 2024-12 | -0.4% | -2.5% | -2.4% |
| 2025-01 | 1.9% | 3.2% | 2.7% |
| 2025-02 | -3.5% | -8.2% | -1.3% |
| 2025-03 | -5.3% | -7.5% | -5.6% |
| 2025-04 | 1.3% | 2.5% | -0.9% |
| 2025-05 | 7.1% | 12.5% | 6.3% |
| 2025-06 | 4.3% | 6.7% | 5.1% |
| 2025-07 | 1.9% | 3.5% | 2.3% |
| 2025-08 | -1.8% | -0.7% | 2.1% |

### From Ondo live date

- Strategy: 17.8% CAGR, -11.1% max DD, 14.4% vol, 0.96 Sharpe, 19.5% total
- Equal-weight buy-and-hold: 36.8% CAGR, -16.8% max DD, 25.7% vol, 1.36 Sharpe, 40.6% total
- SPY: 18.1% CAGR, -8.9% max DD, 12.6% vol, 1.39 Sharpe, 19.8% total
- QQQ (extra): 27.7% CAGR, -12.0% max DD, 19.3% vol, 1.37 Sharpe, 30.5% total

| Month | Strategy | Equal-weight | SPY |
|---|---:|---:|---:|
| 2025-08 | 0.0% | 0.0% | 0.0% |
| 2025-09 | 2.1% | 7.9% | 3.6% |
| 2025-10 | 1.5% | 6.4% | 2.4% |
| 2025-11 | -0.9% | -1.9% | 0.2% |
| 2025-12 | 0.3% | 0.9% | 0.1% |
| 2026-01 | 3.7% | 6.5% | 1.5% |
| 2026-02 | 0.4% | 2.4% | -0.9% |
| 2026-03 | -3.1% | -7.1% | -4.9% |
| 2026-04 | 7.8% | 13.8% | 10.5% |
| 2026-05 | 3.2% | 3.9% | 5.3% |
| 2026-06 | 7.8% | 11.1% | -1.0% |
| 2026-07 | -5.7% | -10.1% | 0.0% |
| 2026-08 | -1.3% | 1.3% | 2.7% |
| 2026-09 | 3.2% | 2.2% | -0.3% |

## Risk-off and caution

Stress cuts were checked on the in-sample half only. Out-of-sample episodes are reported with the same cuts.

In-sample sessions: risk-off 6, caution 65, neutral 16, risk-on 163. Out-of-sample sessions: risk-off 39, caution 105, neutral 30, risk-on 77. A day count versus the peak is a lead when the warning is earlier. Days versus the low are how early the warning sat before the trough.

| Regime | Start | End | Sessions | Sample |
|---|---|---|---:|---|
| caution | 2024-10-03 | 2024-10-15 | 9 | in_sample |
| caution | 2024-10-23 | 2024-10-23 | 1 | in_sample |
| caution | 2024-10-28 | 2024-10-30 | 3 | in_sample |
| caution | 2024-11-01 | 2024-11-06 | 4 | in_sample |
| caution | 2024-12-18 | 2024-12-19 | 2 | in_sample |
| caution | 2024-12-27 | 2025-01-16 | 13 | in_sample |
| caution | 2025-02-26 | 2025-03-04 | 5 | in_sample |
| caution | 2025-03-10 | 2025-04-02 | 18 | in_sample |
| risk-off | 2025-04-03 | 2025-04-10 | 6 | in_sample |
| caution | 2025-05-12 | 2025-05-14 | 3 | in_sample |
| caution | 2025-06-11 | 2025-06-20 | 7 | in_sample |
| caution | 2025-10-16 | 2025-10-17 | 2 | out_of_sample |
| caution | 2025-11-17 | 2025-11-19 | 3 | out_of_sample |
| risk-off | 2025-11-20 | 2025-12-05 | 11 | out_of_sample |
| caution | 2025-12-08 | 2026-01-02 | 18 | out_of_sample |
| caution | 2026-01-14 | 2026-01-14 | 1 | out_of_sample |
| caution | 2026-01-29 | 2026-03-02 | 22 | out_of_sample |
| risk-off | 2026-03-03 | 2026-03-13 | 9 | out_of_sample |
| caution | 2026-03-16 | 2026-03-17 | 2 | out_of_sample |
| risk-off | 2026-03-18 | 2026-03-18 | 1 | out_of_sample |
| caution | 2026-03-19 | 2026-03-19 | 1 | out_of_sample |
| risk-off | 2026-03-20 | 2026-04-07 | 12 | out_of_sample |
| caution | 2026-04-24 | 2026-05-04 | 7 | out_of_sample |
| caution | 2026-05-15 | 2026-05-19 | 3 | out_of_sample |
| caution | 2026-06-02 | 2026-06-02 | 1 | out_of_sample |
| risk-off | 2026-06-03 | 2026-06-10 | 6 | out_of_sample |
| caution | 2026-06-11 | 2026-07-24 | 30 | out_of_sample |
| caution | 2026-08-11 | 2026-08-12 | 2 | out_of_sample |
| caution | 2026-08-20 | 2026-08-20 | 1 | out_of_sample |
| caution | 2026-09-01 | 2026-09-16 | 11 | out_of_sample |
| caution | 2026-09-30 | 2026-09-30 | 1 | out_of_sample |

Large drawdowns are a peak-to-trough of at least 8% in SPY or 15% in BTC. The search window starts 10 equity sessions before the peak and ends at the trough.

| Asset | Sample | Peak | Trough | Depth | Caution | Risk-off | Caution vs peak | Risk-off vs peak | Caution vs low | Risk-off vs low |
|---|---|---|---|---:|---|---|---|---|---|---|
| SPY | in_sample | 2025-02-19 | 2025-04-08 | -18.8% | 2025-02-26 | 2025-04-03 | 7d after peak | 43d after peak | 41d before the low | 5d before the low |
| SPY | out_of_sample | 2026-01-27 | 2026-03-30 | -8.9% | 2026-01-14 | 2026-03-03 | 13d before peak | 35d after peak | 75d before the low | 27d before the low |
| BTC | in_sample | 2025-01-21 | 2025-04-08 | -28.1% | 2025-01-03 | 2025-04-03 | 18d before peak | 72d after peak | 95d before the low | 5d before the low |
| BTC | out_of_sample | 2025-10-06 | 2026-06-30 | -53.1% | 2025-10-16 | 2025-11-20 | 10d after peak | 45d after peak | 257d before the low | 222d before the low |

## Three versions

v1 is the original level rule (risk-off almost never fired). v2 is the stress score with hysteresis and caution, which raised cash and did not redeploy it. v3 keeps that stress score and adds the buy-the-low release: three tranches into the quality name and the high-beta name that fell most and have started to bounce, and BTC longs only on that signal with puts only on a fresh warning. CAGR / max drawdown / Sharpe. Benchmarks are the same in every version.

| Version | Sample | Strategy | Equal-weight | SPY | Deriv hit | Deriv P&L | Stock entries vs low | BTC entry vs low |
|---|---|---|---|---|---:|---:|---|---|
| v1 | full | 27.2% / -24.5% / 0.98 | 28.3% / -28.3% / 1.07 | 17.2% / -18.8% / 1.05 | 38.9% | 14.3% | no buys near the lows | 55.2% above the trough across 2 drawdowns |
| v1 | in sample | 13.2% / -16.6% / 0.59 | 26.2% / -28.3% / 1.00 | 18.7% / -18.8% / 0.98 | 44.4% | 19.5% | no buys near the lows | 22.4% above the trough across 1 drawdown |
| v1 | out of sample | 42.9% / -24.5% / 1.26 | 30.4% / -16.8% / 1.14 | 15.7% / -8.9% / 1.19 | 33.3% | -5.2% | no buys near the lows | 88.0% above the trough across 1 drawdown |
| v2 | full | 13.5% / -15.5% / 0.69 | 28.3% / -28.3% / 1.07 | 17.2% / -18.8% / 1.05 | 29.4% | -30.8% | no buys near the lows | 60.0% above the trough across 2 drawdowns |
| v2 | in sample | 9.1% / -15.5% / 0.39 | 26.2% / -28.3% / 1.00 | 18.7% / -18.8% / 0.98 | 33.3% | -16.7% | no buys near the lows | 32.0% above the trough across 1 drawdown |
| v2 | out of sample | 18.0% / -11.2% / 0.95 | 30.4% / -16.8% / 1.14 | 15.7% / -8.9% / 1.19 | 27.3% | -14.2% | no buys near the lows | 88.0% above the trough across 1 drawdown |
| v3 | full | 14.4% / -15.5% / 0.73 | 28.3% / -28.3% / 1.07 | 17.2% / -18.8% / 1.05 | 29.4% | 1.6% | 10.6% above the trough across 3 drawdowns | 9.4% above the trough across 1 drawdown |
| v3 | in sample | 11.7% / -15.5% / 0.55 | 26.2% / -28.3% / 1.00 | 18.7% / -18.8% / 0.98 | 25.0% | 2.8% | 10.6% above the trough across 3 drawdowns | 9.4% above the trough across 1 drawdown |
| v3 | out of sample | 17.1% / -11.1% / 0.89 | 30.4% / -16.8% / 1.14 | 15.7% / -8.9% / 1.19 | 33.3% | -1.2% | no buys near the lows | no buys near the lows |

Entry versus low is the average fill divided by the price on the trough day, minus one. Zero would be buying the low. Stock rows use buys from the peak through three weeks after the trough. BTC uses the long opened by that version, if any.


## What moved before the drawdowns

Major drawdowns are 8% for SPY and the equal-weight core book, 15% for BTC and for each core name. Each signal is scored from the close, with a 10-session lookback before the peak. Stock signals are the VIX, credit, the 30-year, oil and the dollar. Crypto signals are funding and DVOL. A signal is marked noise when at least half of its in-sample triggers fell outside these drawdown windows. Scheduled FOMC, CPI and payroll dates are noise as a timing tool: a multi-week decline almost always contains one.

In-sample noise labels: event.

### SPY in sample: 2025-02-19 to 2025-04-08 (-18.8%)

Stock side moved first via VIX at or above 25 on 2025-03-10 (19d after the peak, 29d before the low).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2025-03-03 (12d after the peak, 36d before the low).
All hits: dvol_jump 2025-03-03 (12d after the peak, specific), funding 2025-03-07 (16d after the peak, specific), vix_level 2025-03-10 (19d after the peak, specific), credit 2025-03-10 (19d after the peak, specific), vix_jump 2025-04-03 (43d after the peak, specific).
Calendar events inside the window: 6. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-04-08 at 52.3, first fade 2025-04-11 (3d after the low). Credit 20-session change back to flat 2025-05-02 (24d after the low). DVOL peak 2025-03-04 (35d before the low). Funding negative 2025-03-07 (32d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### SPY out of sample: 2026-01-27 to 2026-03-30 (-8.9%)

Stock side moved first via Dollar up 1.5% over 20 sessions on 2026-02-25 (29d after the peak, 33d before the low). Earlier in the lookback: WTI up 8% over 5 sessions on 2026-01-14 (13d before the peak).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2026-02-02 (6d after the peak, 56d before the low).
All hits: oil 2026-01-14 (13d before the peak, specific), dvol_jump 2026-02-02 (6d after the peak, specific), dvol_level 2026-02-05 (9d after the peak, no in-sample triggers), funding 2026-02-06 (10d after the peak, specific), dollar 2026-02-25 (29d after the peak, specific), vix_jump 2026-03-06 (38d after the peak, specific), vix_level 2026-03-06 (38d after the peak, specific), credit 2026-03-19 (51d after the peak, specific).
Calendar events inside the window: 7. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-03-27 at 31.1, first fade 2026-03-31 (1d after the low). Credit 20-session change back to flat 2026-04-06 (7d after the low). DVOL peak 2026-02-05 (53d before the low). Funding negative 2026-02-06 (52d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### equal-weight book in sample: 2024-12-17 to 2025-04-08 (-27.5%)

Stock side moved first via VIX 5-session jump of 6 points or more on 2024-12-18 (1d after the peak, 111d before the low). Earlier in the lookback: Dollar up 1.5% over 20 sessions on 2024-12-03 (14d before the peak).
Crypto side moved first via 7-day BTC funding sum negative on 2025-03-07 (80d after the peak, 32d before the low). Earlier in the lookback: DVOL up 5 points over 5 sessions on 2024-12-05 (12d before the peak).
All hits: dollar 2024-12-03 (14d before the peak, specific), dvol_jump 2024-12-05 (12d before the peak, specific), vix_jump 2024-12-18 (1d after the peak, specific), vix_level 2024-12-18 (1d after the peak, specific), yield_30y 2024-12-27 (10d after the peak, specific), funding 2025-03-07 (80d after the peak, specific), credit 2025-03-10 (83d after the peak, specific).
Calendar events inside the window: 12. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-04-08 at 52.3, first fade 2025-04-11 (3d after the low). Credit 20-session change back to flat 2025-05-02 (24d after the low). DVOL peak 2025-01-19 (79d before the low). Funding negative 2025-03-07 (32d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### equal-weight book out of sample: 2025-10-29 to 2025-11-20 (-9.5%)

Stock side had no print on or after the peak. The lookback did catch Dollar up 1.5% over 20 sessions on 2025-10-15 (14d before the peak).
Crypto side moved first via 7-day BTC funding sum negative on 2025-11-10 (12d after the peak, 10d before the low).
All hits: dollar 2025-10-15 (14d before the peak, specific), vix_jump 2025-10-16 (13d before the peak, specific), vix_level 2025-10-16 (13d before the peak, specific), funding 2025-11-10 (12d after the peak, specific), dvol_jump 2025-11-20 (22d after the peak, specific).
Calendar events inside the window: 3. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-11-20 at 26.4, first fade 2025-11-24 (4d after the low). Credit 20-session change back to flat 2025-12-01 (11d after the low). DVOL peak 2025-11-22 (2d after the low). Funding negative 2025-11-10 (10d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### equal-weight book out of sample: 2026-01-29 to 2026-03-30 (-12.4%)

Stock side moved first via Dollar up 1.5% over 20 sessions on 2026-02-25 (27d after the peak, 33d before the low). Earlier in the lookback: WTI up 8% over 5 sessions on 2026-01-14 (15d before the peak).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2026-02-02 (4d after the peak, 56d before the low).
All hits: oil 2026-01-14 (15d before the peak, specific), dvol_jump 2026-02-02 (4d after the peak, specific), dvol_level 2026-02-05 (7d after the peak, no in-sample triggers), funding 2026-02-06 (8d after the peak, specific), dollar 2026-02-25 (27d after the peak, specific), vix_jump 2026-03-06 (36d after the peak, specific), vix_level 2026-03-06 (36d after the peak, specific), credit 2026-03-19 (49d after the peak, specific).
Calendar events inside the window: 7. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-03-27 at 31.1, first fade 2026-03-31 (1d after the low). Credit 20-session change back to flat 2026-04-06 (7d after the low). DVOL peak 2026-02-05 (53d before the low). Funding negative 2026-02-06 (52d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### equal-weight book out of sample: 2026-05-29 to 2026-07-29 (-9.2%)

Stock side moved first via VIX 5-session jump of 6 points or more on 2026-06-05 (7d after the peak, 54d before the low). Earlier in the lookback: WTI up 8% over 5 sessions on 2026-05-15 (14d before the peak).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2026-06-02 (4d after the peak, 57d before the low). Earlier in the lookback: 7-day BTC funding sum negative on 2026-05-19 (10d before the peak).
All hits: oil 2026-05-15 (14d before the peak, specific), funding 2026-05-19 (10d before the peak, specific), dvol_jump 2026-06-02 (4d after the peak, specific), vix_jump 2026-06-05 (7d after the peak, specific), dollar 2026-06-05 (7d after the peak, specific).
Calendar events inside the window: 5. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-06-10 at 22.2, first fade 2026-06-12 (47d before the low). Credit 20-session change back to flat 2026-08-11 (13d after the low). DVOL peak 2026-06-07 (52d before the low). Funding negative 2026-06-04 (55d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### BTC in sample: 2025-01-21 to 2025-04-08 (-28.1%)

Stock side moved first via VIX at or above 25 on 2025-03-10 (48d after the peak, 29d before the low). Earlier in the lookback: 30-year yield up 35bp over 20 sessions on 2025-01-03 (18d before the peak).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2025-03-03 (41d after the peak, 36d before the low).
All hits: yield_30y 2025-01-03 (18d before the peak, specific), dollar 2025-01-03 (18d before the peak, specific), dvol_jump 2025-03-03 (41d after the peak, specific), funding 2025-03-07 (45d after the peak, specific), vix_level 2025-03-10 (48d after the peak, specific), credit 2025-03-10 (48d after the peak, specific), vix_jump 2025-04-03 (72d after the peak, specific).
Calendar events inside the window: 9. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-04-08 at 52.3, first fade 2025-04-11 (3d after the low). Credit 20-session change back to flat 2025-05-02 (24d after the low). DVOL peak 2025-03-04 (35d before the low). Funding negative 2025-03-07 (32d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### BTC out of sample: 2025-10-06 to 2026-06-30 (-53.1%)

Stock side moved first via Dollar up 1.5% over 20 sessions on 2025-10-09 (3d after the peak, 264d before the low).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2025-10-10 (4d after the peak, 263d before the low).
All hits: dollar 2025-10-09 (3d after the peak, specific), dvol_jump 2025-10-10 (4d after the peak, specific), credit 2025-10-13 (7d after the peak, specific), vix_jump 2025-10-16 (10d after the peak, specific), vix_level 2025-10-16 (10d after the peak, specific), funding 2025-11-10 (35d after the peak, specific), oil 2026-01-14 (100d after the peak, specific), dvol_level 2026-02-05 (122d after the peak, no in-sample triggers).
Calendar events inside the window: 22. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-03-27 at 31.1, first fade 2026-03-31 (91d before the low). Credit 20-session change back to flat 2026-07-01 (1d after the low). DVOL peak 2026-02-05 (145d before the low). Funding negative 2025-11-10 (232d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### MSFT in sample: 2024-12-17 to 2025-04-08 (-21.8%)

Stock side moved first via VIX 5-session jump of 6 points or more on 2024-12-18 (1d after the peak, 111d before the low). Earlier in the lookback: Dollar up 1.5% over 20 sessions on 2024-12-03 (14d before the peak).
Crypto side moved first via 7-day BTC funding sum negative on 2025-03-07 (80d after the peak, 32d before the low). Earlier in the lookback: DVOL up 5 points over 5 sessions on 2024-12-05 (12d before the peak).
All hits: dollar 2024-12-03 (14d before the peak, specific), dvol_jump 2024-12-05 (12d before the peak, specific), vix_jump 2024-12-18 (1d after the peak, specific), vix_level 2024-12-18 (1d after the peak, specific), yield_30y 2024-12-27 (10d after the peak, specific), funding 2025-03-07 (80d after the peak, specific), credit 2025-03-10 (83d after the peak, specific).
Calendar events inside the window: 12. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-04-08 at 52.3, first fade 2025-04-11 (3d after the low). Credit 20-session change back to flat 2025-05-02 (24d after the low). DVOL peak 2025-01-19 (79d before the low). Funding negative 2025-03-07 (32d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### MSFT out of sample: 2025-10-28 to 2026-06-25 (-34.5%)

Stock side moved first via WTI up 8% over 5 sessions on 2026-01-14 (78d after the peak, 162d before the low). Earlier in the lookback: Dollar up 1.5% over 20 sessions on 2025-10-14 (14d before the peak).
Crypto side moved first via 7-day BTC funding sum negative on 2025-11-10 (13d after the peak, 227d before the low). Earlier in the lookback: DVOL up 5 points over 5 sessions on 2025-10-14 (14d before the peak).
All hits: dollar 2025-10-14 (14d before the peak, specific), dvol_jump 2025-10-14 (14d before the peak, specific), vix_jump 2025-10-16 (12d before the peak, specific), vix_level 2025-10-16 (12d before the peak, specific), funding 2025-11-10 (13d after the peak, specific), oil 2026-01-14 (78d after the peak, specific), dvol_level 2026-02-05 (100d after the peak, no in-sample triggers), credit 2026-03-19 (142d after the peak, specific).
Calendar events inside the window: 20. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-03-27 at 31.1, first fade 2026-03-31 (86d before the low). Credit 20-session change back to flat 2026-07-01 (6d after the low). DVOL peak 2026-02-05 (140d before the low). Funding negative 2025-11-10 (227d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### META in sample: 2025-02-14 to 2025-04-21 (-34.2%)

Stock side moved first via VIX at or above 25 on 2025-03-10 (24d after the peak, 42d before the low).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2025-03-03 (17d after the peak, 49d before the low).
All hits: dvol_jump 2025-03-03 (17d after the peak, specific), funding 2025-03-07 (21d after the peak, specific), vix_level 2025-03-10 (24d after the peak, specific), credit 2025-03-10 (24d after the peak, specific), vix_jump 2025-04-03 (48d after the peak, specific).
Calendar events inside the window: 7. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-04-08 at 52.3, first fade 2025-04-11 (10d before the low). Credit 20-session change back to flat 2025-05-02 (11d after the low). DVOL peak 2025-03-04 (48d before the low). Funding negative 2025-03-07 (45d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### META in sample: 2025-08-12 to 2026-03-27 (-33.3%)

Stock side moved first via High-yield OAS wider by 40bp over 20 sessions on 2025-10-13 (62d after the peak, 165d before the low). Earlier in the lookback: Dollar up 1.5% over 20 sessions on 2025-07-29 (14d before the peak).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2025-10-10 (59d after the peak, 168d before the low).
All hits: dollar 2025-07-29 (14d before the peak, specific), dvol_jump 2025-10-10 (59d after the peak, specific), credit 2025-10-13 (62d after the peak, specific), vix_jump 2025-10-16 (65d after the peak, specific), vix_level 2025-10-16 (65d after the peak, specific), funding 2025-11-10 (90d after the peak, specific), oil 2026-01-14 (155d after the peak, specific), dvol_level 2026-02-05 (177d after the peak, no in-sample triggers).
Calendar events inside the window: 21. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-03-27 at 31.1, first fade 2026-03-31 (4d after the low). Credit 20-session change back to flat 2026-04-06 (10d after the low). DVOL peak 2026-02-05 (50d before the low). Funding negative 2025-11-10 (137d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### FCX in sample: 2024-10-02 to 2025-04-04 (-42.2%)

Stock side moved first via WTI up 8% over 5 sessions on 2024-10-03 (1d after the peak, 183d before the low).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2024-11-04 (33d after the peak, 151d before the low).
All hits: oil 2024-10-03 (1d after the peak, specific), yield_30y 2024-10-08 (6d after the peak, specific), dollar 2024-10-10 (8d after the peak, specific), dvol_jump 2024-11-04 (33d after the peak, specific), vix_jump 2024-12-18 (77d after the peak, specific), vix_level 2024-12-18 (77d after the peak, specific), funding 2025-03-07 (156d after the peak, specific), credit 2025-03-10 (159d after the peak, specific).
Calendar events inside the window: 17. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-04-08 at 52.3, first fade 2025-04-11 (7d after the low). Credit 20-session change back to flat 2025-05-02 (28d after the low). DVOL peak 2025-01-19 (75d before the low). Funding negative 2025-03-07 (28d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### FCX out of sample: 2026-02-25 to 2026-03-20 (-24.3%)

Stock side moved first via Dollar up 1.5% over 20 sessions on 2026-02-25 (on the peak, 23d before the low).
Crypto side had no print on or after the peak. The lookback did catch 7-day BTC funding sum negative on 2026-02-10 (15d before the peak).
All hits: funding 2026-02-10 (15d before the peak, specific), dvol_jump 2026-02-24 (1d before the peak, specific), dollar 2026-02-25 (on the peak, specific), oil 2026-03-03 (6d after the peak, specific), vix_jump 2026-03-06 (9d after the peak, specific), vix_level 2026-03-06 (9d after the peak, specific), credit 2026-03-19 (22d after the peak, specific).
Calendar events inside the window: 4. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-03-27 at 31.1, first fade 2026-03-31 (11d after the low). Credit 20-session change back to flat 2026-04-06 (17d after the low). DVOL peak 2026-03-08 (12d before the low). Funding negative 2026-02-25 (23d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### FCX out of sample: 2026-04-22 to 2026-05-04 (-21.0%)

Stock side moved first via WTI up 8% over 5 sessions on 2026-04-24 (2d after the peak, 10d before the low).
Crypto side had no print on or after the peak. The lookback did catch 7-day BTC funding sum negative on 2026-04-15 (7d before the peak).
All hits: funding 2026-04-15 (7d before the peak, specific), oil 2026-04-24 (2d after the peak, specific).
Calendar events inside the window: 3. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-04-23 at 19.3, first fade 2026-04-27 (7d before the low). Credit 20-session change back to flat 2026-05-04 (on the low). DVOL peak 2026-04-22 (12d before the low). Funding negative 2026-04-22 (12d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### FCX out of sample: 2026-06-02 to 2026-07-08 (-19.8%)

Stock side moved first via VIX 5-session jump of 6 points or more on 2026-06-05 (3d after the peak, 33d before the low). Earlier in the lookback: WTI up 8% over 5 sessions on 2026-05-18 (15d before the peak).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2026-06-02 (on the peak, 36d before the low). Earlier in the lookback: 7-day BTC funding sum negative on 2026-05-19 (14d before the peak).
All hits: oil 2026-05-18 (15d before the peak, specific), funding 2026-05-19 (14d before the peak, specific), dvol_jump 2026-06-02 (on the peak, specific), vix_jump 2026-06-05 (3d after the peak, specific), dollar 2026-06-05 (3d after the peak, specific).
Calendar events inside the window: 4. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-06-10 at 22.2, first fade 2026-06-12 (26d before the low). Credit 20-session change back to flat 2026-07-08 (on the low). DVOL peak 2026-06-07 (31d before the low). Funding negative 2026-06-04 (34d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### BAC in sample: 2025-02-06 to 2025-04-04 (-27.5%)

Stock side moved first via VIX at or above 25 on 2025-03-10 (32d after the peak, 25d before the low).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2025-03-03 (25d after the peak, 32d before the low).
All hits: dvol_jump 2025-03-03 (25d after the peak, specific), funding 2025-03-07 (29d after the peak, specific), vix_level 2025-03-10 (32d after the peak, specific), credit 2025-03-10 (32d after the peak, specific), vix_jump 2025-04-03 (56d after the peak, specific).
Calendar events inside the window: 7. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-04-08 at 52.3, first fade 2025-04-11 (7d after the low). Credit 20-session change back to flat 2025-05-02 (28d after the low). DVOL peak 2025-03-04 (31d before the low). Funding negative 2025-03-07 (28d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### BAC out of sample: 2026-01-06 to 2026-03-13 (-17.9%)

Stock side moved first via WTI up 8% over 5 sessions on 2026-01-14 (8d after the peak, 58d before the low).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2026-02-02 (27d after the peak, 39d before the low).
All hits: oil 2026-01-14 (8d after the peak, specific), dvol_jump 2026-02-02 (27d after the peak, specific), dvol_level 2026-02-05 (30d after the peak, no in-sample triggers), funding 2026-02-06 (31d after the peak, specific), dollar 2026-02-25 (50d after the peak, specific), vix_jump 2026-03-06 (59d after the peak, specific), vix_level 2026-03-06 (59d after the peak, specific).
Calendar events inside the window: 7. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-03-27 at 31.1, first fade n/a (n/a). Credit 20-session change back to flat 2026-04-06 (24d after the low). DVOL peak 2026-02-05 (36d before the low). Funding negative 2026-02-06 (35d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### BAC out of sample: 2026-08-12 to 2026-09-30 (-15.6%)

Stock side moved first via Dollar up 1.5% over 20 sessions on 2026-09-21 (40d after the peak, 9d before the low). Earlier in the lookback: WTI up 8% over 5 sessions on 2026-08-11 (1d before the peak).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2026-08-21 (9d after the peak, 40d before the low).
All hits: oil 2026-08-11 (1d before the peak, specific), dvol_jump 2026-08-21 (9d after the peak, specific), dollar 2026-09-21 (40d after the peak, specific), credit 2026-09-29 (48d after the peak, specific), yield_30y 2026-09-30 (49d after the peak, specific).
Calendar events inside the window: 6. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-09-10 at 17.8, first fade 2026-09-17 (13d before the low). Credit 20-session change back to flat n/a (n/a). DVOL peak 2026-08-24 (37d before the low). Funding did not go negative between the peak and the low. There is no volume series in the panel, so capitulation volume cannot be tested.

### AMZN in sample: 2025-02-04 to 2025-04-21 (-30.9%)

Stock side moved first via VIX at or above 25 on 2025-03-10 (34d after the peak, 42d before the low).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2025-03-03 (27d after the peak, 49d before the low).
All hits: dvol_jump 2025-03-03 (27d after the peak, specific), funding 2025-03-07 (31d after the peak, specific), vix_level 2025-03-10 (34d after the peak, specific), credit 2025-03-10 (34d after the peak, specific), vix_jump 2025-04-03 (58d after the peak, specific).
Calendar events inside the window: 8. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-04-08 at 52.3, first fade 2025-04-11 (10d before the low). Credit 20-session change back to flat 2025-05-02 (11d after the low). DVOL peak 2025-03-04 (48d before the low). Funding negative 2025-03-07 (45d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### AMZN out of sample: 2025-11-03 to 2026-02-13 (-21.7%)

Stock side moved first via VIX 5-session jump of 6 points or more on 2025-11-18 (15d after the peak, 87d before the low). Earlier in the lookback: Dollar up 1.5% over 20 sessions on 2025-10-21 (13d before the peak).
Crypto side moved first via 7-day BTC funding sum negative on 2025-11-10 (7d after the peak, 95d before the low).
All hits: dollar 2025-10-21 (13d before the peak, specific), funding 2025-11-10 (7d after the peak, specific), vix_jump 2025-11-18 (15d after the peak, specific), vix_level 2025-11-20 (17d after the peak, specific), dvol_jump 2025-11-20 (17d after the peak, specific), oil 2026-01-14 (72d after the peak, specific), dvol_level 2026-02-05 (94d after the peak, no in-sample triggers).
Calendar events inside the window: 10. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-11-20 at 26.4, first fade 2025-11-24 (81d before the low). Credit 20-session change back to flat 2026-03-04 (19d after the low). DVOL peak 2026-02-05 (8d before the low). Funding negative 2025-11-10 (95d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### AMZN out of sample: 2026-05-06 to 2026-07-29 (-17.6%)

Stock side moved first via VIX 5-session jump of 6 points or more on 2026-06-05 (30d after the peak, 54d before the low). Earlier in the lookback: WTI up 8% over 5 sessions on 2026-04-24 (12d before the peak).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2026-06-02 (27d after the peak, 57d before the low). Earlier in the lookback: 7-day BTC funding sum negative on 2026-04-22 (14d before the peak).
All hits: funding 2026-04-22 (14d before the peak, specific), oil 2026-04-24 (12d before the peak, specific), dvol_jump 2026-06-02 (27d after the peak, specific), vix_jump 2026-06-05 (30d after the peak, specific), dollar 2026-06-05 (30d after the peak, specific).
Calendar events inside the window: 8. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-06-10 at 22.2, first fade 2026-06-12 (47d before the low). Credit 20-session change back to flat 2026-08-11 (13d after the low). DVOL peak 2026-06-07 (52d before the low). Funding negative 2026-05-19 (71d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### EQIX in sample: 2024-12-06 to 2025-12-04 (-24.6%)

Stock side moved first via VIX 5-session jump of 6 points or more on 2024-12-18 (12d after the peak, 351d before the low). Earlier in the lookback: Dollar up 1.5% over 20 sessions on 2024-11-21 (15d before the peak).
Crypto side moved first via 7-day BTC funding sum negative on 2025-03-07 (91d after the peak, 272d before the low). Earlier in the lookback: DVOL up 5 points over 5 sessions on 2024-12-05 (1d before the peak).
All hits: dollar 2024-11-21 (15d before the peak, specific), dvol_jump 2024-12-05 (1d before the peak, specific), vix_jump 2024-12-18 (12d after the peak, specific), vix_level 2024-12-18 (12d after the peak, specific), yield_30y 2024-12-27 (21d after the peak, specific), funding 2025-03-07 (91d after the peak, specific), credit 2025-03-10 (94d after the peak, specific), oil 2025-05-12 (157d after the peak, specific).
Calendar events inside the window: 31. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-04-08 at 52.3, first fade 2025-04-11 (237d before the low). Credit 20-session change back to flat 2025-12-04 (on the low). DVOL peak 2025-01-19 (319d before the low). Funding negative 2025-03-07 (272d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### TSLA in sample: 2024-10-01 to 2024-10-23 (-17.2%)

Stock side moved first via WTI up 8% over 5 sessions on 2024-10-03 (2d after the peak, 20d before the low).
No crypto signal fired in the lookback.
All hits: oil 2024-10-03 (2d after the peak, specific), yield_30y 2024-10-08 (7d after the peak, specific), dollar 2024-10-10 (9d after the peak, specific).
Calendar events inside the window: 2. Treated as noise, not a lead.
Bottom marks: VIX peaked 2024-10-31 at 23.2, first fade 2024-11-06 (14d after the low). Credit 20-session change back to flat 2024-10-23 (on the low). DVOL peak 2024-11-04 (12d after the low). Funding did not go negative between the peak and the low. There is no volume series in the panel, so capitulation volume cannot be tested.

### TSLA in sample: 2024-12-17 to 2025-04-08 (-53.8%)

Stock side moved first via VIX 5-session jump of 6 points or more on 2024-12-18 (1d after the peak, 111d before the low). Earlier in the lookback: Dollar up 1.5% over 20 sessions on 2024-12-03 (14d before the peak).
Crypto side moved first via 7-day BTC funding sum negative on 2025-03-07 (80d after the peak, 32d before the low). Earlier in the lookback: DVOL up 5 points over 5 sessions on 2024-12-05 (12d before the peak).
All hits: dollar 2024-12-03 (14d before the peak, specific), dvol_jump 2024-12-05 (12d before the peak, specific), vix_jump 2024-12-18 (1d after the peak, specific), vix_level 2024-12-18 (1d after the peak, specific), yield_30y 2024-12-27 (10d after the peak, specific), funding 2025-03-07 (80d after the peak, specific), credit 2025-03-10 (83d after the peak, specific).
Calendar events inside the window: 12. Treated as noise, not a lead.
Bottom marks: VIX peaked 2025-04-08 at 52.3, first fade 2025-04-11 (3d after the low). Credit 20-session change back to flat 2025-05-02 (24d after the low). DVOL peak 2025-01-19 (79d before the low). Funding negative 2025-03-07 (32d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

### TSLA out of sample: 2025-12-16 to 2026-07-29 (-39.1%)

Stock side moved first via WTI up 8% over 5 sessions on 2026-01-14 (29d after the peak, 196d before the low).
Crypto side moved first via DVOL up 5 points over 5 sessions on 2026-02-02 (48d after the peak, 177d before the low).
All hits: oil 2026-01-14 (29d after the peak, specific), dvol_jump 2026-02-02 (48d after the peak, specific), dvol_level 2026-02-05 (51d after the peak, no in-sample triggers), funding 2026-02-06 (52d after the peak, specific), dollar 2026-02-25 (71d after the peak, specific), vix_jump 2026-03-06 (80d after the peak, specific), vix_level 2026-03-06 (80d after the peak, specific), credit 2026-03-19 (93d after the peak, specific).
Calendar events inside the window: 19. Treated as noise, not a lead.
Bottom marks: VIX peaked 2026-03-27 at 31.1, first fade 2026-03-31 (120d before the low). Credit 20-session change back to flat 2026-08-11 (13d after the low). DVOL peak 2026-02-05 (174d before the low). Funding negative 2026-02-06 (173d before the low). There is no volume series in the panel, so capitulation volume cannot be tested.

Reading the in-sample tape: the deep equity low was a VIX and credit event, not an oil or 30-year event. Funding turning negative and the DVOL rise showed up in the crypto book during the decline, weeks before the low, so they are stress markers rather than bottom markers. The usable bottom was the VIX falling off a spike of 25 or more while the index was still about 12% under its 60-session high. Waiting for credit to tighten again missed the turn.


## What to improve next

Out of sample, v3 does not beat equal-weight on Sharpe. The April 2025 rebound is not an edge to size up. Out of sample it does not beat v2 on Sharpe either.

The in-sample buys filled 11% above the troughs. The 12% gate did not fire out of sample, so there is no out-of-sample redeploy to judge. Once the release cooled, the strength rule sold the high-beta sleeve. The rebound was only partly held. The next test is to keep those shares until the following caution, instead of refilling cash on the first quiet up-days. That test has not been run.

Credit tightening lagged the in-sample low by weeks, so it stays a confirmation rather than an entry. Funding turning negative marked the middle of the BTC decline, not the turn. The panel has no volume, so a capitulation-volume rule is untested. The 12% drawdown gate was set because the shallower March 2025 fade failed in sample. A rule aimed at later, smaller dips would be a new claim, not a tweak of this one. The crypto P&L is one April 2025 long plus warning puts; the puts lose more often than they pay. Puts are still Black-Scholes on a 30-day DVOL, and same-close fills remain.


## Crypto derivatives

v3 drops the monthly long/short bet. A put is opened only when the regime steps up into caution or risk-off, and it is marked through the buy-the-low day or month-end. A long is opened only on the buy-the-low signal while BTC is still in a drawdown, with the same stop, and held for the configured number of sessions or to month-end. Puts are Black-Scholes on Deribit DVOL when that print exists, otherwise realized vol. Each expression is still scaled as a fraction of one BTC.

Full sample: hit rate 29.4% on 17 active months, sum of monthly P&L 1.6%, worst -3.3%, best 12.6%, perp hit rate 100.0%, put hit rate 23.5%, stops 0.

In sample: hit rate 25.0% on 8 active months, sum of monthly P&L 2.8%, worst -3.3%, best 12.6%, perp hit rate 100.0%, put hit rate 12.5%, stops 0.

Out of sample: hit rate 33.3% on 9 active months, sum of monthly P&L -1.2%, worst -1.8%, best 2.5%, perp hit rate n/a, put hit rate 33.3%, stops 0.

| Month | Signal | Position | Entry | Exit | P&L | Success |
|---|---|---|---:|---:|---:|---|
| 2024-10 | caution / warning put | flat 0 +put | 60759 | 70215 | -2.76% | no |
| 2024-11 | caution / warning put | flat 0 +put | 69482 | 97462 | -3.26% | no |
| 2024-12 | caution / warning put | flat 0 +put | 100042 | 93429 | 0.64% | yes |
| 2025-01 | caution / flat | flat 0  | 96887 | 102405 | 0.00% | n/a |
| 2025-02 | caution / warning put | flat 0 +put | 84347 | 84373 | -0.26% | no |
| 2025-03 | caution / warning put | flat 0 +put | 78532 | 82549 | -2.55% | no |
| 2025-04 | neutral / warning put + bottom long | long 1 +put | 83405 | 94207 | 12.63% | yes |
| 2025-05 | caution / warning put | flat 0 +put | 102813 | 103999 | -0.98% | no |
| 2025-06 | caution / warning put | flat 0 +put | 108687 | 107135 | -0.69% | no |
| 2025-07 | risk-on / flat | flat 0  | 105698 | 115758 | 0.00% | n/a |
| 2025-08 | risk-on / flat | flat 0  | 113320 | 108411 | 0.00% | n/a |
| 2025-09 | risk-on / flat | flat 0  | 111201 | 114056 | 0.00% | n/a |
| 2025-10 | caution / warning put | flat 0 +put | 108186 | 109556 | -1.16% | no |
| 2025-11 | caution / warning put | flat 0 +put | 92094 | 90919 | -0.55% | no |
| 2025-12 | risk-off / flat | flat 0  | 86322 | 87509 | 0.00% | n/a |
| 2026-01 | caution / warning put | flat 0 +put | 96929 | 84129 | 2.47% | yes |
| 2026-02 | caution / flat | flat 0  | 78689 | 65882 | 0.00% | n/a |
| 2026-03 | risk-off / warning put | flat 0 +put | 68294 | 68233 | -1.77% | no |
| 2026-04 | caution / warning put | flat 0 +put | 77455 | 76304 | -0.18% | no |
| 2026-05 | caution / warning put | flat 0 +put | 79066 | 73373 | 0.38% | yes |
| 2026-06 | caution / warning put | flat 0 +put | 66704 | 58559 | 1.62% | yes |
| 2026-07 | caution / flat | flat 0  | 60004 | 62814 | 0.00% | n/a |
| 2026-08 | caution / warning put | flat 0 +put | 63552 | 78549 | -0.93% | no |
| 2026-09 | caution / warning put | flat 0 +put | 77404 | 83554 | -1.05% | no |

## Current book snapshot

As of 2026-09-30, about $798.0: MSFT 15.6%, META 15.5%, FCX 14.4%, BAC 13.1%, AMZN 12.9%, EQIX 12.5%, USDC 15.6%.

Snapshot only. No cost basis exists before 2026-09-15, so the backtest does not replay this book.

Trade-log comparison (plus or minus 5 days): 2026-09-23 sell TSLA recognized as already exited on 2025-05-12 (499 days earlier). Simulated position was already flat. Last simulated sell was 2025-05-12, 499 days earlier. The model sells this name on strength before the logged date, so the log is the same exit, not a same-week fill.

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
- Porto rules. Cash target is 35, 40, 42 or 45 percent in risk-on, neutral, caution and risk-off. An up day in the index raises the target by one step, capped at 45 percent. Adds are only ETN, CAT, APH and AMAT, only in the bottom half of the trailing buy zone, and never in caution or risk-off, on an FOMC decision date, or on an oil-shock day. Trims follow TSLA, FCX, BAC, then half of META, EQIX and MSFT, then a light AMZN trim. A name that is down on the day is not sold. Nothing is sold on a hard-down index day. Two of the three trim gates must pass; on daily bars the regular-hours gate always passes. There is no daily rebalance back to equal weight.
- The regime can block adds and move the cash target. Caution is the middle tier: higher cash, no new adds, a flat perp. It does not authorize selling into a red name or a hard-down day, and it does not by itself short BTC.
- Risk-off is a stress score with hysteresis, not a pillar-level rule. Points come from a VIX jump, credit-spread widening, a 30-year yield breakout, an oil shock, and a BTC drawdown. Enter risk-off at 4, leave it below 2; enter caution at 2, leave it below 1. Red rates plus red volatility or red credit is only an entry backstop. v3 leaves that caution when VIX falls off a spike of 25 or more while SPY is still 12% under its 60-session high, then buys up to three tranches and does not trim while the release is on. The release ends once the stress score cools below the caution exit, so the next rise can raise cash again. The 12% gate is the in-sample distinction between the failed March 2025 fade and the April low. It was not lowered to catch a later, smaller dip.
- Parameters otherwise live in config/market_check.toml. The out-of-sample split is the second half of the window, same parameters.
- Phillip's private numeric bands are not in the repo. The daily check uses the bottom quartile of the trailing range and shifts it with the regime. That is a stand-in.
- The September 2026 book snapshot is printed for context. There is no cost basis before 15 September 2026, so the backtest does not replay that book. An optional trade-log CSV is only a comparison.
- One path, one parameter set, and real approximation error on options, funding and same-close fills. A better in-sample number would not, by itself, be evidence to size up.

## Data

Panel series: 36. Sources: {'AMAT': 'Yahoo Finance AMAT adjusted close', 'AMZN': 'Yahoo Finance AMZN adjusted close', 'APH': 'Yahoo Finance APH adjusted close', 'BAC': 'Yahoo Finance BAC adjusted close', 'BE': 'Yahoo Finance BE adjusted close', 'CAT': 'Yahoo Finance CAT adjusted close', 'CRWD': 'Yahoo Finance CRWD adjusted close', 'DDOG': 'Yahoo Finance DDOG adjusted close', 'EQIX': 'Yahoo Finance EQIX adjusted close', 'ETN': 'Yahoo Finance ETN adjusted close', 'FCX': 'Yahoo Finance FCX adjusted close', 'META': 'Yahoo Finance META adjusted close', 'MRVL': 'Yahoo Finance MRVL adjusted close', 'MSFT': 'Yahoo Finance MSFT adjusted close', 'SPCX': 'Yahoo Finance SPCX adjusted close', 'TSLA': 'Yahoo Finance TSLA adjusted close', 'VST': 'Yahoo Finance VST adjusted close', 'brent': 'FRED DCOILBRENTEU', 'btc': 'Yahoo Finance BTC-USD adjusted close', 'dollar': 'Yahoo Finance DX-Y.NYB adjusted close', 'dvol': 'Deribit BTC DVOL daily close', 'fed_funds': 'New York Fed EFFR', 'funding_daily': 'Deribit BTC-PERPETUAL sum of hourly interest_1h', 'gold': 'Yahoo Finance GC=F adjusted close', 'hy_oas': 'FRED BAMLH0A0HYM2', 'hyg': 'Yahoo Finance HYG adjusted close', 'ig_oas': 'FRED BAMLC0A0CM', 'lqd': 'Yahoo Finance LQD adjusted close', 'qqq': 'Yahoo Finance QQQ adjusted close', 'spy': 'Yahoo Finance SPY adjusted close', 'tlt': 'Yahoo Finance TLT adjusted close', 'vix': 'FRED VIXCLS', 'wti': 'FRED DCOILWTICO', 'yield_10y': 'US Treasury daily par yield curve', 'yield_2y': 'US Treasury daily par yield curve', 'yield_30y': 'US Treasury daily par yield curve'}.

Sessions before the Ondo live date are marked as a 1:1 underlying proxy. The same slippage is charged the whole way; the split is reported separately.
