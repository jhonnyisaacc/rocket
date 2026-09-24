# Hyperliquid close-flow source and economic scout

Status: `TWO_FIXED_MIRROR_SAMPLES_AUDITED`, 2026-09-24. Two free 2025 block-fill
mirror shards were acquired and structurally audited before the FUT-010 rule
was frozen and scored; its result is linked below.

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

An [author presentation from May 2026](https://drive.google.com/file/d/1qUTWDaL6j-cWBO8myGAg7cGxLjMBLs3C/view)
clarifies the cohort mechanism (slides 17 and 20): front-end wallets use
`FrontendMarket` orders, have short active sessions, and submit few orders.
It calls this an observable behavioral label, with 97.5% of users never
switching labels in its sample. That retrospective stability statistic is
**not** permission to use a full-sample label at an earlier decision time.
The fill mirror contains `oid` but no order `tif`, so it cannot establish
which closing fills came from `FrontendMarket` orders or build the stated
wallet cohort by itself. Historical order records with wallet, `oid`, `tif`,
timestamp and complete enough prior activity must be joined to fills, with
the label computed only from prior orders.

The presentation's HYPE chart (slide 47) shows close-loser taker mid-price
markouts diverging by roughly 5–10 bp more from 30 to 120 minutes than at
30 minutes, and the three wallet cohorts have broadly similar curves when
conditioned on close-loser state. This is a visual reading of an earlier
paper version, **not** a precise delayed-entry BTC/ETH return or a costed
forecast. It suggests that a predeclared longer-horizon, state-conditioned
trial could be more discriminating than simply adding a wallet label to
the already failed 30-minute FUT-010 rule; it cannot rescue that rule.

## Historical access and timing

The [official historical-data page](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data)
points to `s3://hl-mainnet-node-data/node_fills_by_block`; older fills are
under `node_fills` in a different format. It also lists `replica_cmds` for
historical L1 transactions, a possible order-intent source. A [public mirror
of its object inventory](https://huggingface.co/datasets/gionuibk/hyperliquid-replica-cmds)
exists, but it has not been sampled for `FrontendMarket`, wallet/`oid`
joinability, or time coverage. The official archive says requester pays
transfer costs. L2 snapshots are in a separate `hyperliquid-archive` bucket, with
possible gaps and delayed uploads. The [user-fill API](https://hyperliquid.gitbook.io/Hyperliquid-docs/for-developers/api/info-endpoint)
returns at most 2,000 fills per response and makes only the 10,000 most
recent fills per user available. That API is a schema/live spot-check path,
not a complete historical market-wide panel. An earlier anonymous L2 HEAD
probe returned 403; see the [order-book scout](ORDERBOOK_SOURCE_SCOUT.md).
No billed S3 request or transfer was made here.

The [official order-status API](https://hyperliquid.gitbook.io/Hyperliquid-docs/for-developers/api/info-endpoint#query-order-status-by-oid-or-cloid)
exposes an order's `tif`, including `FrontendMarket`, when given wallet and
`oid`. Its `historicalOrders` listing returns only the 2,000 most recent
orders per wallet; neither endpoint is yet verified as a complete 2025
market-wide cohort history. A narrow `orderStatus` spot check for fixed
fill `oid`s is a cheaper first joinability test than acquiring the whole
`replica_cmds` archive.

That check was run on the first three distinct BTC/ETH unmarked loss-close
taker wallet/`oid` pairs in each of the two fixed 2025 shards. All six
requests returned `unknownOid` on 2026-09-24, including three July and
three October orders. The 42-character wallets and order IDs came directly
from the mirror fills, and no post-event price was read for this check.
This is evidence that the public API did not recover those historical
orders; it does not prove that the official `replica_cmds` archive or a
separately recorded order stream lacks them. The reason for `unknownOid`
was not determined. Do not use a live/current order-status lookup to
backfill a claimed point-in-time cohort without an archival completeness
and timestamp test.

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

The same return-free auditor run with `--coins HYPE` found 401,208 HYPE
wallet-fill rows, 200,604 two-counterparty trade keys, 39,173 unmarked
loss-realizing taker closes, and no selected missing fields on this July
shard. This is source feasibility for the asset in the author chart, not
an evaluated HYPE strategy or a count of independent signals.

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

The HYPE-only return-free audit on the October shard found 190,092
wallet-fill rows, 95,046 two-counterparty trade keys, 23,559 unmarked
loss-realizing taker closes, and no selected missing fields. Its same
large block gap still applies. These two already inspected dates are
useful source checks, but a new 120-minute HYPE contract should freeze
fresh discovery dates before reading HYPE outcomes.

### Fresh HYPE 120-minute source windows

Before any HYPE future return was read, mirror metadata led to fixed
September batch cutoffs, then the HYPE-only structural auditor determined
their actual contiguous hours. The [September 1 cutoff shard](https://huggingface.co/datasets/gionuibk/hyperliquid-node-fills-by-block/resolve/main/data/batch_upto_20250901_0.lz4_1765112048.parquet)
(SHA-256 `77a3d0689948c14114eed15e53e05f1b02c1d8080172b54675122e634601d143`)
contains 2025-08-31 UTC hours `03`–`09` continuously; 32,716 HYPE unmarked
loss-realizing taker closes occur across the **whole shard**, with no
selected missing fields and all 109,958 HYPE trade keys paired. The
[September 29 cutoff shard](https://huggingface.co/datasets/gionuibk/hyperliquid-node-fills-by-block/resolve/main/data/batch_upto_20250929_0.lz4_1765117407.parquet)
(SHA-256 `c858ffcfca963b858ed3d696f569b38178bbfec1fdb897adca8cd7a6ccc75a0a`)
contains 2025-09-28 UTC hours `03`–`09` continuously; 22,771 qualifying
HYPE closes occur across its whole shard, with no selected missing fields
and all 74,368 HYPE trade keys paired. Each shard has one gap **outside**
the selected seven-hour segment. Both chosen windows are Sundays and share
the same UTC clock, 28 days apart. The [FUT-011 contract](experiments/FUT-011.md)
froze only these windows before scoring. Its subsequent
[result](experiments/FUT-011-RESULT.md) failed the two-date gross/incremental
gate; August was below the base fee floor and September lagged always-short.

A preselected September 15 cutoff shard was source-audited but not chosen:
its 2025-09-14 and 2025-09-15 hours were split into roughly two-hour
segments by two block gaps, leaving inadequate room for the intended
120-minute hold and delayed entry. This exclusion used only block coverage,
not HYPE prices or returns. The later September 29 shard replaced it
under that coverage criterion.

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
The May 2026 author presentation supplies a qualitative 120-minute HYPE
markout, but no precise delayed-entry BTC/ETH effect size or executable
threshold for FUT-010.

**Decision:** the free 2025 mirror resolves the initial field and event-count
gate on the two audited shards. Its completeness, exact source fidelity and
spread/depth remain unverified. The subsequent [FUT-010 result](experiments/FUT-010-RESULT.md)
failed the base-fee-floor gate for the exact all-wallet delayed rule. The
source paper's front-end label is now partially specified by its author
presentation, but historical order fields and a point-in-time join remain
unverified. The chart's HYPE markout is insufficient to infer a costed
delayed BTC/ETH return. The 2026 final holdout remains unread.
