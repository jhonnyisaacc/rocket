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

## Full 2020–2022 candidate inventory

The resumable `research/futures/bybit_coverage.py` then queried all **190** catalog USDT perpetuals with reported launch before 2023 (126 currently trading, 64 closed), saving **2,468** raw daily/funding API pages and their SHA-256 hashes. This is the complete set under that *current-catalog* rule, not proof that the catalog preserves every historical delisting. The [funding-history endpoint](https://bybit-exchange.github.io/docs/v5/market/history-fund-rate) caps a page at 200 records; the inventory paginates backward to the beginning of each requested window. An initial uncapped attempt understated funding coverage and was discarded before this report.

| Year | Observed daily bars | Funding observations | Price days with same-day funding | Symbols with paired days |
| --- | ---: | ---: | ---: | ---: |
| 2020 | 516 | 1,757 | 516 | 5 |
| 2021 | 8,791 | 28,755 | 8,791 | 103 |
| 2022 | 58,414 | 219,067 | 58,414 | 190 |

Across the 190 names, the observed 67,721 daily bars have **zero internal calendar gaps** between each symbol's first and last bar; all have a funding timestamp on the same day, and no adjacent funding timestamps within a symbol are more than eight hours apart. All API requests completed. A few funding records exist outside observed price coverage: ETHUSDT funding starts in October 2020 although its first API daily bar is March 2021, and LUNAUSDT funding extends past its last May 2022 daily bar. Funding alone never grants eligibility. The old `launchTime` discrepancies in the sample remain; observed bars and funding must define the usable period.

This supports 2022 as a potential broad independent-venue research window with 2021 warmup; 2020 has only five observed names. It does **not** yet establish a valid strategy test: lagged liquidity, 121-day history, closed-contract settlement, symbol mapping, cost and actual venue execution still require independent rules. Ignored local coverage report SHA-256: `6c5cc40b569d117c14c7565e63c7bf9d78464876b445e66aa11347b60a7a31c7`.

## Causal 2022 eligibility preflight

`research/futures/bybit_eligibility.py` verified every raw page against the inventory hash and checked 121 consecutive, tradable completed daily bars, lagged 30-day average USDT turnover of at least $5 million, and complete prior funding before each 2022 entry decision. It inspected no portfolio returns. Of 69,160 symbol/day candidates (190 names × 364 scoreable entry dates), **15,509** pass eligibility across **106** symbols; 26,848 lack complete prior history, 26,801 fail turnover, and two lack prior funding. One BCH first-day bar has zero open/low despite positive volume and is explicitly marked nontradable.

Four potentially exposed data issues remain: LUNA May 12–13, FTT November 13, and SRM November 15. They involve missing next-day opens or held funding after the last observed bar. The May 13 LUNA order has no entry fill and must remain cash; a held prior position needs a venue-specific forced settlement outcome. These issues cannot be dropped or filled with a flat bar. Ignored local preflight SHA-256: `c0125af203b76b5d94221242182159eecf7d2b3c18ab9c1db0855fa7cc2dfa3d`.

The [official Hyperliquid historical-data page](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data) provides archived L2 snapshots and asset contexts but says candles are not offered in its S3 archive; downloads charge the requester. The API's [candle snapshot](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint) is limited to recent history. A broad full-history Hyperliquid reconstruction from public node fills would be a different, larger data project. Hyperliquid remains the intended execution venue, so any surviving candidate still needs its own overlap and prospective shadow there.

The next gate is contract-specific cessation handling, a venue-specific cost rule, and a **distinct frozen gross-signal hypothesis** before any Bybit strategy outcome. The 2022 candidate tape now has a measured point-in-time eligibility rule. Define symbol mapping and the new strategy question before examining returns. No 2026 Binance final-holdout bars should be inspected for candidate selection.
