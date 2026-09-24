# Intraday order-flow source scout

Status: `SAMPLE_ONLY`, 2026-09-24. This is a fixed read-only source check,
not FUT-006, a frozen direction rule or a return study.

[Kim and Hansen (2026)](https://arxiv.org/abs/2607.09426) use Binance
USD-M aggregate trades for six liquid perpetuals during January 2021–October
2024. They report that quarter-hour opening order imbalance has predictive
content at four-to-twelve-hour horizons. Their evidence is a mechanism prior,
not a net strategy result for Rocket or a Hyperliquid transfer result. The
[official Binance public-data description](https://github.com/binance/binance-public-data/blob/master/README.md)
maps futures `aggTrades` to `/fapi/v1/aggTrades` and defines the last field
as whether the buyer was the maker. Thus `false` represents a
buyer-initiated aggregate trade and `true` a seller-initiated one, consistent
with the paper's construction. Aggregate trades are not individual fills or
top-of-book execution quotes.

HEAD requests confirmed public daily BTCUSDT and ETHUSDT ZIPs at the study
boundary (2024-10-31) and at both endpoints of calendar 2025. A subsequent
[S3 inventory](../../../research/futures/orderflow_archive_inventory.py)
listed **all 365 daily ZIPs and 365 matching checksum objects per contract**
for 2025, with no missing dates. Its deterministic local manifest SHA-256 is
`2edc76210261facbd2c77a39c5fccf6a1a0b744afa5e0ea7fd2445e20225c27c`.
Listed compressed ZIP bytes total **6.70 GB BTC and 9.94 GB ETH**, or
16.64 GB together, before decompression. S3 object presence does not prove
correct row continuity or checksum content. The fixed January 1, 2025
BTC/ETH ZIPs and their official `.CHECKSUM` files were downloaded. The
[source probe](../../../research/futures/orderflow_source_probe.py) checked
the exact seven-column schema, official ZIP SHA-256, UTC day bounds,
nondecreasing timestamps and aggregate IDs, consecutive aggregate IDs,
positive price/quantity, and both taker-side flag values without computing
any imbalance or forward return.

| Contract | Rows | Covered minutes | Ordering or ID gaps | Official ZIP SHA-256 |
| --- | ---: | ---: | ---: | --- |
| BTCUSDT | 726,611 | 1,440 / 1,440 | 0 | `b0e75563f195609cc12369dca095f3dcb26ed84fc4e1234c9b91a807a5d51202` |
| ETHUSDT | 816,837 | 1,440 / 1,440 | 0 | `7f682c4cc8a362e7a11c7adcd9e1b4e5f30debad5eb796407c6d785c95a4ae6c` |

The ignored local sample report SHA-256 is
`c490d19429c98f73e9950aff8df060c0d2f6887240a704b1cf8eb7017cb64a59`.
Both days have nonzero counts for both `is_buyer_maker` values and no
nonpositive-quantity rows. One clean day does not establish full historical
continuity or a viable intraday forecast. Before a rule is frozen, inventory
every needed day and checksum, audit cross-day ID continuity and timestamp
coverage, verify the actual phase and release/decision delay, choose a fixed
early falsifier and reserve 2025 as a post-study chronology. Funding, spread,
impact, latency, position overlap, and Hyperliquid order-flow compatibility
remain essential later gates. The 2026 Binance holdout remains untouched.

The paper measures imbalance over the **first ten seconds** of each quarter
hour; a one-minute candle would blend in the next fifty seconds and cannot
be called an exact reconstruction. HEAD probes for official BTC/ETH `1s`
USD-M futures kline ZIPs on 2025-01-01 returned 404. Aggregate trades are
therefore the verified raw source for that ten-second question at this point.
The 16.64 GB acquisition is feasible in the current workspace only with
streamed parsing and disk-space checks; it is not an edge or promotion gate.
