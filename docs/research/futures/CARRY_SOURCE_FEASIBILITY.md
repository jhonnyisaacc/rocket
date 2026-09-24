# Cross-venue perpetual carry source feasibility

Status: `SAMPLE_ONLY`, 2026-09-24. This is a source and product-fit check, not
FUT-005, a frozen trading rule, or an inspected carry return.

The [Hyperliquid historical funding endpoint](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals#retrieve-historical-funding-rates)
exposes coin, funding rate, premium and payment timestamp. Funding is
[hourly](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding).
The [candle endpoint](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint#candle-snapshot)
documents a 5,000-candle recency limit; daily candles can be queried for
older dates, whereas historical hourly candles cannot be assumed available
for a long test. The S3 [historical-data page](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data)
lists asset contexts and L2 snapshots, warns of possible missing data, and
does not supply a separate candle archive. Binance's already acquired and
checksum-verified futures tape contains BTCUSDT and ETHUSDT daily prices and
funding across 2024–2025. This gives a plausible source pair, not a valid
paired strategy dataset yet.

`research/futures/hyperliquid_carry_source_probe.py` requested fixed BTC and
ETH windows on January 1–2 of 2024 and 2025. Each of the four windows had
48 distinct hourly Hyperliquid funding slots and two distinct daily candles.
The candle response also included a third candle at the requested end
boundary, so downstream code must enforce an explicit half-open interval.
Raw responses are retained in ignored local research data; the eight raw
response SHA-256 hashes are recorded in the probe output. The probe checked
time order, slots, contract symbols, candle bounds and non-duplicated rows.
It computed no price, funding or strategy returns. Full-history continuity,
publication timing, price convention, revision risk and delistings remain
unverified.

A long Binance perp / short Hyperliquid perp pair would collect the difference
in funding only when Hyperliquid funding paid to the short exceeds Binance
funding paid by the long. Its total P&L also includes changes in the two
perpetual prices and four execution legs at opening and closing. It requires
capital and margin on two venues, USDT/USDC collateral treatment, liquidation
and transfer-risk accounting, and explicit execution support outside the
current single-venue Rocket decision path. Hyperliquid's
[contract specification](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/contract-specifications)
calls out USDC margin for USDT-denominated linear contracts; treating this
as identical to Binance USDT collateral without a conversion or stress is
unjustified. Its [base perp taker fee](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
is 0.045% per fill at the zero-volume tier, before spread and impact.

Before freezing a carry test, establish a full historical paired tape and
explicitly decide whether two-venue hedge decisions fit the requested
`rocket crypto scan --json` contract. Predeclare contract mapping, base-size
matching, decision/publication lag, funding sign and timestamp convention,
mark and fill prices, rebalancing, venue-specific fees and spread/impact,
collateral accounting, venue outage and liquidation rules, calendar split,
and a cheap *net* falsifier. A positive funding spread alone is not a net
strategy result. No 2026 holdout or current live position has been inspected.
