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
