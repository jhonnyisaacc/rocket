# Independent venue data source scout

Status: `SAMPLED_COVERAGE_AUDITED`, 2026-09-24. This is a read-only source check, not a strategy outcome or a declared independent validation sample.

The [official Bybit V5 kline endpoint](https://bybit-exchange.github.io/docs/v5/market/kline) returned BTCUSDT linear perpetual daily candles for June 1–2, 2020, and the [official funding-history endpoint](https://bybit-exchange.github.io/docs/v5/market/history-fund-rate) returned four funding timestamps over the same interval. Thus an earlier, independent venue has at least one observed price/funding overlap. API bars and funding are paginated; one successful symbol/day does not establish a complete broad historical tape.

The [official instruments endpoint](https://bybit-exchange.github.io/docs/v5/market/instrument) exposes `contractType`, `status`, `launchTime`, `deliveryTime`, pagination, and a `Closed` status. A live two-status catalog audit at 2026-09-24T15:58Z found 777 `Trading` and 306 `Closed` USDT linear perpetuals. The `Closed` response also contained five `PendingOpen` instruments, three of them USDT perpetuals; the audit filters by **returned** status. This is a promising delisting inventory, but current catalog metadata is not a point-in-time universe by itself. Its completeness, past metadata revisions, contract renames, and correspondence with actual first/last bar and funding timestamps remain unverified.

## Measured source sample

`research/futures/bybit_source_audit.py` chose the earliest twelve pre-2023 `Trading` and earliest twelve pre-2023 `Closed` USDT perpetuals by reported launch time. For all 24 it probed the first 30 UTC days and funding records after reported launch; for the twelve closed names it also probed 30 days before reported delivery. Every API response was saved locally with a SHA-256 hash. Results:

| Window group | Sample windows | Full 30 daily bars | Any daily bars and funding | Largest observed gap between adjacent funding records |
| --- | ---: | ---: | ---: | ---: |
| First after reported launch | 24 | 17 | 18 | 8 hours where records exist |
| Last before reported delivery | 12 | 12 | 12 | 8 hours |

Six reported launch windows had neither bars nor funding: BCH, LINK, LTC and XTZ carry a 2018-01-01 reported launch time, and ADA and MATIC had no source rows in their first January 2021 windows. BTC had 20 of 30 daily bars in its March 2020 launch window, with its first observed bar and funding record ten days after the reported launch. Thus launch metadata alone would create fictitious early eligibility; membership must start from observed, completed bars, complete prior funding and a lagged liquidity floor. The 12 closed-contract end windows include LUNA, SRM and FTT around cessation, but their exact settlement prices and delisting rules still need venue-specific treatment.

Ignored local report SHA-256: `85c4224fa25e204df4ac350391467f044c6931e4d650dd97ea8cff9f798bd01c`; source catalog page SHA-256 values: `8ad61666d386655353c30e5915eefd7b147c1d99173d787ddc88e7ee4e96bda4` (`Trading`) and `2ee84553ba85f7a760da0d572380853098158c94db164ee38794332237c52745` (`Closed`). This is a selected coverage sample, not a complete inventory of historical paired days or proof of API completeness for every delisted contract.

The [official Hyperliquid historical-data page](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data) provides archived L2 snapshots and asset contexts but says candles are not offered in its S3 archive; downloads charge the requester. The API's [candle snapshot](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint) is limited to recent history. A broad full-history Hyperliquid reconstruction from public node fills would be a different, larger data project. Hyperliquid remains the intended execution venue, so any surviving candidate still needs its own overlap and prospective shadow there.

The next data gate is a full hash-tracked 2020–2022 Bybit price/funding coverage inventory across observed `Trading` and `Closed` USDT perpetuals, with first/last actual rows, internal gaps, and cessation handling. Define the chronology and symbol mapping before examining a new strategy's Bybit outcomes. No 2026 Binance final-holdout bars should be inspected for candidate selection.
