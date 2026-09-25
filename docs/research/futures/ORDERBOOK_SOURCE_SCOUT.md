# Near-touch order-book source scout

Status: `THREE_FIXED_L2_DAYS_AUDITED`, 2026-09-24. This is a
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
of that archive and fixed early/late comparison days found:

| UTC day | L2 SHA-256 | Bytes | Messages | Maximum adjacent gap |
| --- | --- | ---: | ---: | ---: |
| [2023-04-01](https://static.okx.com/cdn/okx/match/orderbook/L2/400lv/daily/20230401/BTC-USDT-SWAP-L2orderbook-400lv-2023-04-01.tar.gz) | `cb38f07ba8f1770f6d91d9a7fbb020b9031b9888c7e7e2cf8dd438ce9a5e33fc` | 158,897,856 | 5,406,650 | 580 ms |
| [2024-09-01](https://static.okx.com/cdn/okx/match/orderbook/L2/400lv/daily/20240901/BTC-USDT-SWAP-L2orderbook-400lv-2024-09-01.tar.gz) | `437a49aabe412423b2f7ea1d5bd6571eef7f019c108201ead01dca9b2610f788` | 390,010,114 | 7,140,545 | 597 ms |
| [2025-01-01](https://static.okx.com/cdn/okx/match/orderbook/L2/400lv/daily/20250101/BTC-USDT-SWAP-L2orderbook-400lv-2025-01-01.tar.gz) | `2071e7ee70ac47a25eb7eae250e47b4ae8876a7cd6ea1287e377970246ade09c` | 350,454,127 | 7,066,075 | 546 ms |

Each compressed archive contains one `.data` member with the same date
stem, starts within 5 ms of its UTC midnight, ends within 32 ms of the next
midnight, contains 1,440 snapshots, and has records in every UTC minute.
All three had no decreasing or duplicate timestamps, no adjacent gap over
one second, no invalid price/size/order-count levels, and no empty or crossed
best bid/ask in 1,440 minute checks. The reconstructed book reached 400
levels per side. The opening 2024 best-bid raw quantity was 59.2; its
displayed price and size are present. These checks are structural, not a
return calculation.

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
The corresponding adjacent trade ZIP objects for **2023-04-01/02** and
**2025-01-01/02** each returned HTTP 200 to a fixed HEAD check; their bytes
and cross-feed timing have not yet been audited. Separate fixed L2 HEAD
checks returned HTTP 200 for **2024-01-01** (376,662,567 bytes),
**2024-11-01** (463,948,861 bytes) and **2025-12-31** (372,594,332 bytes)
as well as the audited early/late days. These five fixed checks establish
availability across several periods, not continuous coverage between them.

OKX's [2020 face-value adjustment](https://www.okx.com/ua-eu/help/adjustment-of-face-value-for-usdt-margined-perpetual-swap-futures-trading)
specified 0.01 BTC per BTCUSDT perpetual contract. A later
[2021 proposal to change it to 0.001 BTC was postponed](https://www.okx.com/help/postponement-of-face-value-adjustment),
and the [OKX fee FAQ](https://www.okx.com/en-sg/help/trading-fee-rules-faq)
still gives 0.01 BTC in its contract example (published 2024, updated
2026). This supports **0.01 BTC per contract as a working conversion**
for near-touch quantity. It is not an archived instrument specification
from each sampled day, so size-dependent execution modeling must retain
that provenance and check any intervening face-value notice.

The local SHA-256 values identify the downloaded bytes; OKX did not supply
an independent checksum manifest in this check. L2 has no sequence number,
so the observed timestamp coverage and reconstructed book cannot prove that
no update was dropped. Three isolated days cannot establish continuous
multi-year completeness or stability. The sample is from OKX, so a positive
result would still need Hyperliquid transfer and intended-venue
execution-cost checks.

The intended venue's [published base perpetual fee](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
is **4.5 bp per taker fill**, or 9 bp for a two-sided taker round trip before
spread and impact. The existing 5 bp-per-side research stress is therefore
a 10 bp round-trip fee hurdle for a fully opened-and-closed short-horizon
position. The paper's public abstract reports a return/toxicity association,
not a return magnitude after that hurdle. Its passive-buy warning could
inform entry avoidance without being an executable directional taker edge.
This cost comparison is a prior feasibility bound; no conditioned returns
or 2025 strategy outcomes were read.

Next verify timestamp/latency semantics and economic scale before freezing
a pressure/capacity rule; if the mechanism clears that gate, audit matching
trade bytes for the early and late fixed days and map a continuous research
window. Compare plausible forward return with round-trip fees and spread
at its actual horizon. Signed
Hyperliquid access remains a separate venue-transfer path. No strategy or
production decision changes follow from this source audit.
