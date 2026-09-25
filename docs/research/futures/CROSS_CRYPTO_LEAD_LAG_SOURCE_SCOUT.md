# Cross-crypto lead-lag source and economic screen

Status: `SOURCE_CLOCKS_AUDITED`, 2026-09-25. Minute bars were read only
for source integrity and clock coverage. No BTC-conditioned future
return, strategy outcome, signal threshold or parameter was read or
selected in this scout.

## Mechanism and transfer boundary

[Guo, Sang, Tu and Wang's 2024 study](https://www.sciencedirect.com/science/article/pii/S0165188924000551)
finds minute-level cross-cryptocurrency return predictability on Binance
spot: Bitcoin responds promptly to common shocks and its lagged return
helps predict other coins over short horizons. The authors also report
out-of-sample spot portfolios. This motivates a distinct **information
diffusion** question after the trend, basis, order-flow and liquidation
rules tested elsewhere in the pillar. It does not establish that a
minute-lagged forecast survives a completed-bin decision, a subsequent
perpetual fill, repeated fees, spread, slippage or funding. A spot
association cannot be called a perp strategy result.

The cheapest useful falsifier would measure delayed, same-clock
perpetual gross return after a predeclared BTC spot lead, against the
same target coin's unconditional direction and own-lag controls, then
compare it with the intended venue's round-trip cost floor. It needs
nonoverlapping or cluster-aware events, a fixed chronological split,
asset/date breakdown and a self-financing turnover model before any
promotion. No sign, target list, trigger size, minute horizon, or hold
has been frozen here. Selecting them from any forward return would be a
new trial and must be logged.

## Source-only probe

The [official Binance public-data archive](https://github.com/binance/binance-public-data/blob/master/README.md)
had a `.CHECKSUM` object at each of nine preselected monthly one-minute
kline paths. The [source auditor](../../../research/futures/cross_crypto_minute_source_audit.py)
then downloaded the nine ZIPs (17,343,037 bytes), verified every
published SHA-256 sidecar, and pinned the exact source keys, hashes and
row counts in the [manifest](source_manifests/cross_crypto_minute_2024_2025.json):

| UTC month | BTCUSDT spot 1m | ETHUSDT USDT perp 1m | SOLUSDT USDT perp 1m |
| --- | --- | --- | --- |
| 2024-11 | 43,200 / 0 missing | 43,200 / 0 missing | 43,200 / 0 missing |
| 2025-04 | 43,200 / 0 missing | 43,200 / 0 missing | 43,200 / 0 missing |
| 2025-08 | 44,640 / 0 missing | 44,640 / 0 missing | 44,640 / 0 missing |

Every one-minute timestamp in each month is present on all three
markets: **131,040 common minutes**. ZIP rows have valid aligned
open/close intervals and nonnegative volumes. BTC spot uses millisecond
timestamps in November 2024 and microseconds in April/August 2025;
both perps use milliseconds throughout. ETH/SOL have 18/19 zero-base-
volume rows in August; a tradability rule must exclude or bound these
rather than assume executable fills. The ignored local integrity report
SHA-256 is `3b347661fa40ae5b3c81b6ae48415abefc382dbd4ca1bbe4451ff63ae914ec13`.

Complete source clocks do not establish real-time publication latency,
causal spot-to-perp fill timing, bid/ask depth, point-in-time target
eligibility or fees. Next freeze the decision/entry delay, target list,
controls, cost model and chronology before reading BTC-conditioned
forward returns. Keep the 2026 final holdout untouched.
