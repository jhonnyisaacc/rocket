# Near-touch order-book source scout

Status: `SINGLE_DAY_NEAR_TOUCH_SAMPLE_AUDITED`, 2026-09-24. This is a
return-free data and economic-feasibility check, not FUT-008 or an order-book
strategy result. The [candidate paper](https://ssrn.com/abstract=6693260)
reports that recent sell pressure relative to best-bid absorption capacity
predicts short-horizon returns and passive-buy toxicity on Binance BTC
perpetuals. Its public abstract does not supply a costed standalone
directional rule or an effect measured against ordinary taker fees.

The official Binance USD-M `bookDepth` archive had matching ZIP/checksum
objects on fixed **2024-01-01** and **2025-01-01** BTCUSDT days. Both ZIPs
were downloaded and matched their official SHA-256 checksums:

| UTC day | ZIP SHA-256 | Rows | Timestamp groups | Depth bands |
| --- | --- | ---: | ---: | --- |
| 2024-01-01 | `4ca5780b56eaba50363c0a4d486938a3d05e56f0041441fb649ea8c8c8d8e666` | 28,800 | 2,880 | −5% through −1%, +1% through +5% |
| 2025-01-01 | `fa37c9f66c96a95cf3081c5812d8e1d8fdbb0fc0df1c05989fd973492eaebd48` | 28,800 | 2,880 | same |

The four columns are `timestamp,percentage,depth,notional`. Groups arrive
about every 30 seconds with seconds-level timestamps. Their closest
displayed band is **1%** away, not the best bid/ask price and queue size
used for the paper's near-touch absorption concept. These two fixed days do
not establish full-year archive completeness or correct depth semantics.
One open [Binance data-quality issue](https://github.com/binance/binance-public-data/issues/431)
also reports bookDepth/mark-price misalignment, warranting an independent
price-level check before any band-based trial. Replacing best-bid capacity
with ±1% bands would be a different signal and needs its own prior and freeze.

The separate Binance `bookTicker` ZIP/checksum archive contains a fixed
2024-01-01 BTCUSDT object of 128,284,409 compressed bytes. S3 inventory
found daily objects through March 2024 (30 ZIPs that month) but no matching
BTCUSDT objects in April–June 2024 or on fixed 2024-10-31, 2024-11-01,
2024-12-31, 2025-01-01/02/12-31 and 2026-01-01 dates. This is a bounded
availability check, not a proof every intervening date is missing. One
early-2024 ticker day is large, and the checked post-study dates are absent,
so a direct 2025 public-archive transfer is unavailable by this route.
The ticker file was **not** downloaded or schema-audited in this scout.

[Hyperliquid's official historical-data page](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data)
lists hourly `.lz4` L2 book snapshots in a requester-pays S3 bucket and
warns that uploads can be late or incomplete. Anonymous read-only HEAD
requests, including the requester-payer header, returned **HTTP 403** for
fixed BTC 2024-01-01 and 2025-01-01 hour-zero objects. This shows the
anonymous path is not usable in the current environment; it does **not**
show the objects are absent. No signed/requester-billed download was made.

[OKX's official historical-data page](https://www.okx.com/historical-data)
advertises high-resolution L2 order books from March 2023 and tick-level
trades from September 2021. Its public download dialog exposed **Perpetual**
and **BTC-USDT**, with 400- and 5,000-level choices. The browser dialog's
2024-09-01 selection listed a **2024-09-02** L2 filename; the public site's
download-link endpoint, queried with explicit UTC epoch bounds for
**2024-09-01**, returned the [2024-09-01 400-level archive](https://static.okx.com/cdn/okx/match/orderbook/L2/400lv/daily/20240901/BTC-USDT-SWAP-L2orderbook-400lv-2024-09-01.tar.gz).
The archive itself starts at `2024-09-01 00:00:00.005 UTC` and ends at
`23:59:59.978 UTC`, confirming the latter as the correct fixed UTC source.
The page's field-information panel describes `instId`, `action`
(`snapshot` or `update`), ask/bid price, quantity and order count, and `ts`
as a millisecond Unix push timestamp.

The reproducible [streaming audit](../../../research/futures/okx_l2_audit.py)
of that one archive found:

| Fixed BTC-USDT-SWAP UTC day | Evidence |
| --- | --- |
| L2 archive | 390,010,114 compressed bytes; SHA-256 `437a49aabe412423b2f7ea1d5bd6571eef7f019c108201ead01dca9b2610f788`; one 2,803,224,169-byte `.data` member |
| L2 records | 7,140,545 lines: 1,440 snapshots and 7,139,105 updates; every UTC minute represented |
| Ordering and book | No decreasing/duplicate timestamps; maximum adjacent gap 597 ms; 1,440 minute checks found no empty or crossed best bid/ask; reconstructed book reached 400 levels per side |
| Near-touch field | The opening reconstructed best-bid raw quantity was 59.2, showing the best price and its displayed size are present; historical contract-unit conversion is still to verify |

The matching trade feed uses **UTC+8 daily boundaries**. The
[September 1](https://static.okx.com/cdn/okex/traderecords/trades/daily/20240901/BTC-USDT-SWAP-trades-2024-09-01.zip)
and [September 2](https://static.okx.com/cdn/okex/traderecords/trades/daily/20240902/BTC-USDT-SWAP-trades-2024-09-02.zip)
ZIPs are both needed for the L2 UTC day. Their respective SHA-256 digests
are `89e5e30f8ecf7074b40e92eb2dcfe604012083402ec6c1220bc7ab240483fd44`
and `bddb2da7041465f912b232736f961a19847f05060058c67100391003d0f3edd3`.
The two files contain 1,331,285 trades within that UTC day and cover all
1,440 minutes. Their trade IDs are consecutive within and across the files,
and their timestamps are ordered. This establishes a source-level pairing
path, not synchronized exchange event ordering between the two feeds.

The local SHA-256 values identify the downloaded bytes; OKX did not supply
an independent checksum manifest in this check. L2 has no sequence number,
so the observed timestamp coverage and reconstructed book cannot prove that
no update was dropped. One day cannot establish multi-year availability or
stability. The sample is from OKX, so a positive result would still need
Hyperliquid transfer and intended-venue execution-cost checks.

Next verify point-in-time contract units and timestamp/latency semantics,
then check several fixed dates across the intended discovery and transfer
periods before freezing a pressure/capacity rule. Compare plausible forward
return with round-trip fees and spread at its actual horizon. Signed
Hyperliquid access remains a separate venue-transfer path. No strategy or
production decision changes follow from this source audit.
