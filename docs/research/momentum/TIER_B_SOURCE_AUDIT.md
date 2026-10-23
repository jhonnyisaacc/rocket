# Tier B source audit — MOM-DATA-002

Status: `DATA_READINESS_ONLY`; no feature, target, model or strategy scoring.
This independently checks the source claims in Muse PR #50 at
`b8ddbd0d1f477f82f96b26298885b97b0f95e063`. It does not reopen MOM-000 or MOM-001.
The machine evidence is [TIER_B_SOURCE_MANIFEST.json](TIER_B_SOURCE_MANIFEST.json).
Its receipt timestamps are the actual October 2026 audit receipts, not
historical publication times.

## Coverage verified

Every requested archive name and checksum-sidecar name was checked against
the complete, paginated public bucket catalog. Monthly perp and funding ZIPs
were all downloaded and SHA-256 verified, independently of Muse's files.
Daily metrics and premium-index contents were sampled as stated below.
Catalog enumeration also sees names after 2025; no 2026 data contents were
downloaded or used. Availability of a named file does not prove every row is
valid, and a checksum proves byte integrity rather than historical PIT.

| Source | Exact path beneath `https://data.binance.vision/data/` | Requested coverage and verification |
| --- | --- | --- |
| BTCUSDT USD-M perpetual 1h klines | `futures/um/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-{YYYY-MM}.zip` | January 2020–December 2025: 72/72 ZIPs and sidecars, all 72 SHA-256 verified; 52,608 unique aligned hourly opens, no missing hourly opens or duplicate opens in that range |
| Realized funding | `futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-{YYYY-MM}.zip` | January 2020–December 2025: 72/72 ZIPs and sidecars, all 72 SHA-256 verified; 6,576 unique event times and one observation per nominal 8h settlement slot |
| Intraday metrics, including OI | `futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-{YYYY-MM-DD}.zip` | September 1, 2020–December 31, 2025: 1,948/1,948 daily ZIPs and sidecars; three days SHA-256/content verified; the other days' within-file gaps, conflicts and value validity remain unverified |
| Monthly OI/metrics directories | `futures/um/monthly/openInterest/` and `futures/um/monthly/metrics/` | Empty in the public catalog; neither category is listed beneath monthly USD-M data |
| Premium-index 1h klines | `futures/um/monthly/premiumIndexKlines/BTCUSDT/1h/BTCUSDT-1h-{YYYY-MM}.zip` | January 2020–December 2025: 72/72 ZIPs and sidecars; January 2020 and December 2025 SHA-256/content verified |

There are no missing **files** in the three requested Tier B ranges. This
does not certify the entire metrics row history. The first available names in
these checked catalogs are January 2020 for perp/funding/premium and September
1, 2020 for daily metrics. BTC spot candidates before those source ranges
retain missing Tier B inputs; no proxy, backward fill or population deletion
is authorized.

Muse's perp/funding and metrics boundary claims are confirmed. Its statement
that monthly premium-index archives do not exist is incorrect: the proper
category is `premiumIndexKlines`, not `premiumIndex`. The [official monthly
category catalog](https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=%2F&prefix=data%2Ffutures%2Fum%2Fmonthly%2F)
lists it, and the [BTCUSDT 1h catalog](https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=data%2Ffutures%2Fum%2Fmonthly%2FpremiumIndexKlines%2FBTCUSDT%2F1h%2F)
contains the requested objects. Premium-index availability adds no feature to
the frozen packet. Daily metrics provide the checked public archive route to
OI; the audit makes no universal claim about all possible OI sources.

## Timestamp, units and duplicate findings

Perp klines contain millisecond UTC open and close timestamps, base volume
and quote volume. For quote-volume participation, retain BTCUSDT USDT quote
volume, align the same complete spot/perp 24h window, and validate all input
bars. Futures timestamps in the checked period remain milliseconds; the
2025 spot switch to microseconds must not be applied to these futures files.
The [official public-data column definitions](https://github.com/binance/binance-public-data/blob/master/README.md)
provide the source schema.

Funding CSV columns are `calc_time,funding_interval_hours,last_funding_rate`.
All checked interval fields are 8 hours. Of 6,576 observations, 2,882
`calc_time` values lie 1–47ms after the nominal settlement boundary. There
are no missing or duplicate nominal 8h slots. An exact-grid test alone would
wrongly call those observations absent. Retain actual `calc_time` as the
event clock; grouping into a nominal slot here is a completeness diagnostic,
not permission to round availability backward. The realized settlement rate
is different from a predicted rate for the next settlement. The [funding
API documentation](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)
identifies the funding event timestamp.

Daily metrics files contain intraday `create_time` UTC strings, in the samples
every five minutes from 00:00 through 23:55. They contain both
`sum_open_interest` and `sum_open_interest_value`; these measure contract/base
exposure and its notional value respectively. A 24h positioning change must
keep the first definition and compare matching event times. A notional
fallback would mix price movement into the feature and change its definition.
An end-of-day aggregate or flooring all rows to midnight likewise changes a
4h-clock feature into a lagged daily feature; neither is automatically the
frozen 24h OI change.

The September 1, 2020 sample has 576 data rows but only 288 distinct
`create_time` values: every row occurs twice, identically. The January 1,
2023 and December 31, 2025 samples each have 288 rows and unique timestamps.
All three samples cover every expected five-minute snapshot; none has a
conflicting duplicate. A future parser must collapse exact duplicates while
rejecting or quarantining conflicting values with identical source/event/
publication identity. File presence alone would miss this issue.

## Historical PIT and revisions

These are current corrected archive vintages. Actual historical receipt and
per-row publication availability are absent. The bucket's `LastModified`
timestamps frequently postdate the event years; they identify current object
metadata, not original market availability. Preserve the catalog-page hashes,
ZIP hashes, exact source identity and actual audit receipt in the manifest.

Binance's [archive documentation](https://github.com/binance/binance-public-data/blob/master/README.md)
describes later corrections and checksum replacement. Daily/monthly archive
delivery occurs after the covered period. Reconstructing a feature as if a
live market stream were received near its event time therefore requires an
explicit historical availability assumption, independent latency/clock
review and current-vintage disclosure. It is not authenticated historical
PIT. Files acquired now must never carry backdated ingestion timestamps.

The [OI-history API documentation](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)
limits that endpoint to the latest month, so calling it today cannot recreate
2020–2025 original publication vintages. An archive snapshot's `create_time`
is an event/measurement timestamp; it supplies no actual receipt clock.

No Tier B value enters the current canonical spot-only shadow collector.
Before any later authorized MOM-002 scoring, source parsing, complete-window
checks, exact duplicate handling, feature definitions and declared historical
availability must pass the pending independent review. Outside verified
coverage or wherever input/clock evidence is inadequate, retain `UNKNOWN`.
The data-readiness finding is conditional historical reconstruction, not
PIT certification or evidence of predictive information.

## Reproduction and evidence boundary

The manifest records every monthly perp/funding ZIP's URL, SHA-256, first and
last raw row, row count, timestamp coverage; all paginated catalog URLs and
raw-response hashes; every missing requested file/sidecar list; metrics
month-by-month file counts; and sample metrics/premium hashes and raw rows.
The original XML/catalog and downloaded bytes are cached under ignored
`.rocket/momentum/tier-b-audit/`. A future audit can GET the catalog URLs,
follow `NextMarker` (or the last returned key when truncated), compare every
expected name, GET each selected `.CHECKSUM`, then compare SHA-256 against the
ZIP bytes. Sidecar absence, network failure and genuinely absent upstream
objects must remain separate outcomes. A failed request is not proof of
missing coverage.

Only source metadata and raw-source integrity were evaluated. MOM-000 keeps
its original population, labels and `STOP_INSUFFICIENT_FEASIBILITY`.
MOM-002 remains unscored and `PENDING_INDEPENDENT_REVIEW`.
