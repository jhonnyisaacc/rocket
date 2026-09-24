# Near-touch order-book source scout

Status: `HISTORICAL_L2_LISTING_VERIFIED_BYTES_UNAUDITED`, 2026-09-24. This is a
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
and **BTC-USDT**, with 400- and 5,000-level choices. A fixed UTC
**2024-09-01** query at 400 levels returned one listed export,
`BTC-USDT-SWAP-L2orderbook-400lv-2024-09-02.tar.gz`, with a displayed size
of **384.19 MB**. The file-date suffix is one day after the selected period;
the archive's actual coverage must be checked rather than inferred from its
name. The page's field-information panel describes `instId`, `action`
(`snapshot` or `update`), ask/bid price, quantity and order count, and `ts`
as a millisecond Unix push timestamp. That schema is compatible with a
reconstructed best-bid-capacity measure, subject to checking update order,
gaps, snapshot resets, contract units and timestamp alignment against trades.
The listing and field definitions were verified in the UI; archive bytes,
checksum, completeness and downloadable access were **not** validated.
This is also an OKX venue sample, so a positive finding would still need a
separate Hyperliquid transfer and execution-cost check.

Next validate a bounded OKX archive sample: record its digest, unpacked
schema, actual UTC coverage, snapshot/update continuity, best-bid size and
contract units, then pair it with timestamp-compatible trade data. Compare
plausible forward return with round-trip fees/spread before registering a
rule. Signed Hyperliquid access remains an independent venue-transfer path.
If historical L2 bytes are not accessible, prospective collection/shadow is
a distinct path and cannot masquerade as a historical OOS test. No strategy
or production decision changes follow from this scout.
