# Hyperliquid close-flow source and economic scout

Status: `TWO_FIXED_MIRROR_SAMPLES_AUDITED`, 2026-09-24. Two free 2025 block-fill
mirror shards were acquired and structurally audited. No conditioned return was
calculated, and no trade rule was registered.

## Mechanism and observable fields

[Jia et al.](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7270041)
report that the price impact of *voluntary taker* trades by wallets they
classify as front-end traders decays and, after loss-realizing closes,
reverses past zero. This is an event-study result in the public abstract,
not a delayed-entry return or executable strategy result. The abstract does
not give the reversal magnitude, timing, wallet-classification procedure,
or a costed threshold. Its aggregate wallet losses include venue fees; they
are not an estimate of a counterparty trading edge. Forced exits are a
different event type and must not inherit the voluntary-close finding.

[Hyperliquid's fill schema](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions)
has `time`, `coin`, `side`, `px`, `sz`, `closedPnl`, `startPosition`, `crossed`,
`tid`, and an optional `liquidation` object with `method` (`market` or
`backstop`) and `markPx`. `closedPnl < 0` identifies a fill that realizes a
loss in the venue's accounting; `crossed: true` identifies the taker. A
candidate *voluntary* close therefore needs a perpetual fill with negative
`closedPnl`, `crossed: true`, closing direction, and **no liquidation
marker**. A forced-close stream would use the liquidation marker and be
analyzed separately. The [node misc-event schema](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/nodes/l1-data-schemas)
also defines a `Liquidation` ledger delta with affected positions, which
could cross-check identification if matching block data are available.
The documentation establishes the field names, not that every historical
archive version preserves every field or that the marker is complete.

The paper's front-end wallet cohort cannot be recreated by assigning a
wallet its eventual class in the past. Any wallet classifier must be
computable from information available before each event, or the first
source trial must use **all wallets** and acknowledge that it tests a
different, weaker mechanism. Raw `closedPnl` also varies with trade size:
event counts and signed closing notional need separate definitions before
an outcome is read. A closing sell and a closing buy imply opposite
reversal directions; forced liquidations may instead have continuation.
These distinctions prohibit pooling the two into a single signed signal.

## Historical access and timing

The [official historical-data page](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data)
points to `s3://hl-mainnet-node-data/node_fills_by_block`; older fills are
under `node_fills` in a different format. It says requester pays transfer
costs. L2 snapshots are in a separate `hyperliquid-archive` bucket, with
possible gaps and delayed uploads. The [user-fill API](https://hyperliquid.gitbook.io/Hyperliquid-docs/for-developers/api/info-endpoint)
returns at most 2,000 fills per response and makes only the 10,000 most
recent fills per user available. That API is a schema/live spot-check path,
not a complete historical market-wide panel. An earlier anonymous L2 HEAD
probe returned 403; see the [order-book scout](ORDERBOOK_SOURCE_SCOUT.md).
No billed S3 request or transfer was made here.

The original archive must still be cross-checked before any promotion, but a
free mirror now supplies an initial source sample. Decision time must be
**after the complete source block is observed**, with a
specified processing and order-placement delay; a fill's exchange `time`
alone is not proof that the whole block was available then. An executable
backtest needs a contemporaneous entry/exit bid and ask, available depth,
fees, and funding. L2 snapshots alone may not resolve queue or impact.

### Free 2025 mirror: fixed return-free sample

The public [gionuibk block-fill mirror](https://huggingface.co/datasets/gionuibk/hyperliquid-node-fills-by-block)
contains Parquet rows with `block_number`, `block_time`, `local_time`, a JSON
`events` array of wallet/fill pairs, and the original `node_fills_by_block`
hourly path. A metadata-only listing found 1,076 files totaling 113.8 GB;
75 distinct `batch_upto_YYYYMMDD` filename dates run from 2025-07-28 to
2025-10-10. Other files use opaque `universal_data` names, and filename
dates alone do **not** establish complete date coverage or licensing.

We selected the first named 2025-07-28 [Parquet shard](https://huggingface.co/datasets/gionuibk/hyperliquid-node-fills-by-block/resolve/main/data/batch_upto_20250728_17.lz4_1765105625.parquet)
for a source check before any price outcome calculation. The downloaded
233,752,595 bytes have SHA-256
`0fef107456e07dd63785f39b4366612071b1db1295ee03a0be6839ee77a66a69`.
The [streaming source auditor](../../../research/futures/hyperliquid_close_flow_source_audit.py)
(`python research/futures/hyperliquid_close_flow_source_audit.py SHARD.parquet`,
with DuckDB installed) reported:

| Check | Fixed shard result |
| --- | ---: |
| Original UTC hourly source paths | `20250728/14` through `/17` |
| Block UTC time range | 2025-07-28 13:59:59.860357–17:59:59.854673 |
| Blocks; sequence gaps or duplicates | 180,998; 0 |
| All wallet-fill rows | 2,107,936 |
| BTC / ETH wallet-fill rows | 139,954 / 187,120 |
| BTC+ETH distinct trade keys with exactly two counterparties | 163,537 |
| BTC+ETH missing wallet, `tid`, `closedPnl`, `crossed`, or `time` | 0 |
| BTC+ETH marked liquidation fills | 1,654 |
| BTC+ETH unmarked loss-realizing taker closes | 31,596 |
| BTC+ETH marked loss-realizing taker closes | 780 |
| Local receipt minus block time, median / p99 / max | 101.632 / 189.683 / 809.076 ms |

The two-sided fill representation requires counting only the taker close,
not both wallet rows, for a directional event. The liquidation marker appears
on both counterparties; marked events must be excluded from the voluntary
sample. The observed local receipt delay is a historical node observation,
not a guarantee of Rocket's future latency. This is one four-hour mirror
shard, with no independent source checksum, no book quotes and no proof of
continuous coverage. The 2026 mirror was used for schema preview only; no
2026 outcome was read.

We independently selected a later [2025-10-10 shard](https://huggingface.co/datasets/gionuibk/hyperliquid-node-fills-by-block/resolve/main/data/batch_upto_20251010_14.lz4_1765119892.parquet)
before outcomes. Its 241,902,165 bytes have SHA-256
`600e52955d8975614402f25404e141418a54a64e80ca0b016ebf44ccd82f703b`.
The same auditor found 310,040 blocks, 2,011,536 wallet-fill rows, 344,566
BTC/ETH rows, 41,703 unmarked loss-realizing taker closes and 880 marked
liquidation fills. Selected fields were complete and all 172,283 BTC/ETH
trade keys had exactly two counterparties. **There is one material block
sequence break:** block 757948605 is followed by 758304396, leaving 355,790
block numbers absent. Original source paths cover UTC hours `0`, `1`, and
`10`–`14`, but not `2`–`9`. Any pilot must treat these as separate windows and
must not bridge the gap with a position or interpolated price. A mirror
filename can therefore hide a large internal coverage gap; the 75-date
metadata inventory is not a continuous tape guarantee.

A [public explorer block](https://github.com/hyperliquid-dex/node/issues/32)
was also queried as a free alternative. Its `blockDetails` and `txDetails`
responses exposed submitted order actions but no fill outcomes, so it
cannot replace the fill source for this question. Hyperliquid's
[explorer rate limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits)
also direct large historical requests to S3.

## Cost gate before a directional trial

The [published base perpetual taker fee](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
is 4.5 bp per side: **9 bp for entry and exit before spread, market impact,
funding, and latency**. A taker reversal needs a delayed-entry gross move
larger than that total hurdle, not merely a statistically detectable
post-trade price reversal measured from the distressed fill. Any event-study
move measured from before the close includes pressure that occurred before
Rocket could react and cannot be counted as its executable return.

The fixed mirror samples clear the initial field and event-count gate for a
**cheap gross economic pilot on 2025 data**. The [FUT-010 contract](experiments/FUT-010.md)
now freezes event aggregation, observation delay, entry/exit price proxy,
horizon, baseline, sample dates, and falsifier before conditioned returns.
The pilot uses delayed
trade prices as an optimistic gross proxy from the same source tape, while
keeping marked liquidations out of the voluntary sample and comparing with
an unconditional same-side control. If the gross proxy is below the 9 bp
fee floor, close the direction idea before
a full archive purchase. If it clears, cross-check the mirror with official
source bytes and obtain bid/ask and depth evidence before treating it as executable.
There is currently no paper-based effect size that sets the event threshold,
horizon, or wallet cohort.

**Decision:** the free 2025 mirror resolves the initial field and event-count
gate on the two audited shards. Its completeness, exact source fidelity,
spread/depth and economic feasibility remain unverified. The next action is
to score the frozen 2025 gross pilot within verified contiguous source windows;
no FUT-010 result or production change follows from this scout. The 2026
final holdout remains unread.
