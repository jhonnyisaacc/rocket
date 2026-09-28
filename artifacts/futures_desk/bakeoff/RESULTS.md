# Bakeoff results

Phase 3 of the five frozen contracts. Retrieved 2026-09-23T08:37:35Z from `rocket.providers.hyperliquid.fetch_candles` (`candleSnapshot` on `https://api.hyperliquid.xyz/info`). No second client. `execution_enabled` stays false. The live scan was not changed. No parameter was changed. The June 2026 and HYPE windows were not used, because no trades were computed.

## Blocker

The 12-month replay cannot be completed. Do not read the table as zeros.

Window required: completed bars from 2025-09-23T00:00:00Z through 2026-09-23T08:00:00Z, setup on closed 4h, trigger on closed 1h, fill at the next 1h open. Costs 20bps and 40bps plus funding were not applied, because there is no fill tape to apply them to.

`candleSnapshot` for `1h` returns only the most recent 5000 bars. Older windows return an empty list with HTTP 200.

| Request | Coin | Interval | Bars | First open | Last open |
|---|---|---|---|---|---|
| 2025-09-23 → 2026-09-24 | BTC | 1h | 5001 | 2026-02-27T00:00:00Z | 2026-09-23T08:00:00Z |
| 2025-09-23 → 2026-02-01 | BTC | 1h | 0 |  |  |
| 2026-02-26 → 2026-02-28 | BTC | 1h | 25 | 2026-02-27T00:00:00Z | 2026-02-28T00:00:00Z |
| 2025-09-23 → 2026-09-24 | ETH | 1h | 5001 | 2026-02-27T00:00:00Z | 2026-09-23T08:00:00Z |
| 2025-09-23 → 2026-02-01 | ETH | 1h | 0 |  |  |
| 2025-09-23 → 2026-09-24 | HYPE | 1h | 5003 | 2026-02-26T22:00:00Z | 2026-09-23T08:00:00Z |
| 2025-09-23 → 2026-02-01 | HYPE | 1h | 0 |  |  |
| 2025-09-23 → 2026-09-24 | BTC | 4h | 2193 | 2025-09-23T00:00:00Z | 2026-09-23T08:00:00Z |
| 2025-09-23 → 2026-09-24 | BTC | 1d | 366 | 2025-09-23T00:00:00Z | 2026-09-23T00:00:00Z |

ETH 4h and 1d match BTC: 2193 bars and 366 bars, both starting 2025-09-23. HYPE 4h and 1d do too.

Every frozen contract fills at the next 1h open. `CONTRACTS.md` forbids filling that open with a 4h, 1d, or 1w print. From 2025-09-23 through 2026-02-26 the 1h open does not exist in this provider. Substituting the next 4h open, or scoring only 2026-02-27 onward and calling it the 12-month result, would be a different sample. That suffix contains the June 2026 BTC low and the HYPE high and drops the prior five months. It was not run, so it cannot pick a winner.

Funding is not the blocker. `fundingHistory` for BTC from 2025-09-23 returns hourly rates (500 rows per call, first print 2025-09-23T00:00:00.047Z). It was not summed, because there are no fills.

Vintage market-cap ranks are still missing (`rocket/providers/coingecko.py` is live-only). The month-start liquid-perp list was not built. No today's top-100 stamp was applied. No ENTER was counted.

## Table

| Contract | ENTER count | Trades/month | BTC June 2026 low → summer | HYPE ATH window | Net mean R, 20bps + funding | Net mean R, 40bps + funding | Max closed-trade drawdown | Time in market |
|---|---|---|---|---|---|---|---|---|
| `trb-50d` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| `cmom-r3-quintile` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| `pana-full` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| `staged-zone-as-entry` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| `theory-v2-code` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |

Not `NO_SAMPLE`. Admissions were not measured. `NO_SAMPLE` would mean a finished run with about zero admissions.

## What this run can say

Nothing survived, and nothing was shown to be too tight or too loose. The five contracts were not scored. Monthly time-series momentum, Jegadeesh–Titman deciles, volatility scaling, and funding-as-alpha were already left out of `CONTRACTS.md` because they are not 4h-setup / 1h-fill rules. This run does not add a new opinion about them.

Phase 4 did not run. No contract was shown near 0.5–3 trades per month, and none was shown to clear 20bps and 40bps. `NO_EDGE_VALIDATED` is not the result of a blocked tape. No `ENTER_CONTRACT_v1.md`. The live scan still has no `ENTER_*` path from this bakeoff.

## Available 1h tape, not 12 months

The sentence above, "It was not run," describes the pass that wrote the blocker. This section is that suffix. It is the measured 1h tape only. It does not replace the table above and it is not the 12-month result.

Window: 1h opens from 2026-02-27T00:00:00Z through 2026-09-23T08:00:00Z. Elapsed time is 208.333 days, 6.845 months of 365.25/12 days. Fills outside that window are not counted. No 1h bar before 2026-02-27 was invented. HYPE's 2026-02-26T22:00:00Z hour was dropped. The last open, 2026-09-23T08:00:00Z, can be a fill price. Its high and low were not used, because that hour was still open when it was measured. Some names' first returned hour is 2026-02-27T01:00:00Z (AAVE, BCH, DASH, ENA, LINK, LIT, MEGA, SKR, UNI, WLD, XMR, XRP). Later first hours: CHIP 2026-04-22T02:00:00Z, CASHCAT 2026-07-11T04:00:00Z, GRAM 2026-07-02T09:00:00Z, PONS 2026-08-31T03:00:00Z. 4h, 1d, and venue 1w bars the provider returned before 2026-02-27 are warmup for the contracts that name those endpoints. `pana-full` builds its 4h, 1d, and Monday weeks from this 1h tape only.

Universe: currently listed perps only. Delisted names are absent from `metaAndAssetCtxs`. A name is on a month-start list when its last completed `1d` bar at that start has base volume times close at least 5,000,000. That is the live scan's quote-volume floor applied to one daily bar, not today's `dayNtlVlm`. Open interest and spread history are absent and were not filled from today's meta. This is not today's top 100. Month-start counts inside the scored book: 2026-02-27 20, Mar 31, Apr 21, May 19, Jun 20, Jul 24, Aug 17, Sep 30. Every name below had at least 24 closed 1h bars in the window, so the month-start list was usable and no fallback book was substituted.

Scored names: AAVE, ADA, ALGO, ARB, ASTER, AVAX, BCH, BIO, BNB, BTC, CASHCAT, CHIP, CRV, DASH, DOGE, DOT, ENA, ETH, FARTCOIN, GRAM, HYPE, INJ, JTO, KAITO, LINK, LIT, LTC, MEGA, MON, NEAR, ONDO, PAXG, PENGU, PONS, PUMP, PURR, PYTH, SKR, SOL, SUI, TAO, TRUMP, UNI, VIRTUAL, VVV, WIF, WLD, WLFI, XLM, XMR, XPL, XRP, ZEC, ZORA, ZRO, kPEPE.

Costs are 20bps or 40bps of entry notional, half at the fill and half at the exit, plus hourly funding in `(fill, exit]`. A missing funding hour drops that trade from the mean. None were dropped. Trades still open at the last bar are out of the mean and out of the drawdown. Drawdown is the peak-to-trough of the sum of those closed outcomes ordered by exit time. It is not a mark-to-market account. `trb-50d` and `cmom-r3-quintile` have no stop, so R is undefined and the drawdown is on net return. Time in market is the average, across these 56 names, of each name's union of position hours divided by the 6.845-month tape. Names with no trade contribute zero.

June and HYPE columns count ENTER fills only. They are observations. BTC's completed June 2026 daily low was 58062 on the daily that opened 2026-06-25T00:00:00Z. The window runs from that open through 2026-08-31T23:59:59Z. HYPE's completed daily high was 97.816 on the daily that opened 2026-09-22T00:00:00Z. The 2026-09-23 daily was still open at the last 1h and was not used. The observation window is seven days before that open through seven days after, intersected with this tape. The separate 1h-tape high is 97.999.

`cmom-r3-quintile` uses venue `1w` candles. On this pull they open Thursday 00:00 UTC. Weeks were not rebuilt from 4h. Vintage market cap is still missing, so the mean is an unweighted mean of membership events (`weight_unknown_do_not_equal_weight`), not the paper's value-weighted portfolio. `theory-v2-code` was flat at the tape start. OLHC and OHLC produced the same ENTER count, the same mean R, the same drawdown, and the same time in market, so one row is shown. Fires were 4157. Entries are the fires taken while that name was flat and the next open was not through the stop.

| Contract | ENTER count | Trades/month on this tape | BTC June 2026 low → summer | HYPE completed-daily high ± 7d | Net mean, 20bps + funding | Net mean, 40bps + funding | Max closed-trade drawdown | Time in market |
|---|---|---|---|---|---|---|---|---|
| `trb-50d` | 952 | 139.09 | L 179 / S 133 | L 7 / S 0 | R undefined; net return +0.0131 (860 closed) | R undefined; net return +0.0111 (860 closed) | -9.372 overlapping net return | 19.7% |
| `cmom-r3-quintile` | 238 | 34.77 | L 36 / S 36 | L 0 / S 0 | R undefined; unweighted net return +0.0006 (228 closed) | R undefined; unweighted net return -0.0014 (228 closed) | -1.789 overlapping net return | 14.2% |
| `pana-full` | NO_SAMPLE | NO_SAMPLE | NO_SAMPLE | NO_SAMPLE | NO_SAMPLE | NO_SAMPLE | NO_SAMPLE | NO_SAMPLE |
| `staged-zone-as-entry` | 625 | 91.31 | L 72 / S 71 | L 1 / S 0 | R -0.056 (622 closed) | R -0.113 (622 closed) | -52.897 R | 3.0% |
| `theory-v2-code` | 107 | 15.63 | L 11 / S 12 | L 0 / S 0 | R -0.080 (95 closed) | R -0.100 (95 closed) | -25.370 R | 7.8% |

`trb-50d` left 92 events open, `cmom-r3-quintile` 10, `staged-zone-as-entry` 3, and `theory-v2-code` 12. Those are not in the means. `trb-50d` trades/month counts overlapping 10-day events. `cmom-r3-quintile` trades/month counts long and short quintile memberships. Neither figure is a one-position book.

`pana-full` finished and admitted zero hypotheses on every scored name. The frozen flip stack (weekly direction, confirmed daily impulse, zone, reaction, and two objectives together) never cleared, so the row is `NO_SAMPLE`. A BTC frame at the last 4h boundary had weekly velocity 0.56, which is neutral under the frozen ±1.2 rule, and was not eligible.

No winner. Phase 4 stays off. This window was not used to open `ENTER_CONTRACT_v1.md`. `execution_enabled` stays false. The live scan was not changed.
