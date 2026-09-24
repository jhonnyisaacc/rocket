# Hyperliquid close-flow source and economic scout

Status: `SOURCE_GATE_OPEN`, 2026-09-24. No fill archive was acquired, no
conditioned return was calculated, and no trade rule was registered.

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

The archive must be sampled before a strategy freeze to verify the actual
envelope, wallet attribution, `liquidation` coverage, deduplication key,
perpetual-versus-spot filtering, UTC/block chronology, and gaps. Decision
time must be **after the complete source block is observed**, with a
specified processing and order-placement delay; a fill's exchange `time`
alone is not proof that the whole block was available then. An executable
backtest needs a contemporaneous entry/exit bid and ask, available depth,
fees, and funding. L2 snapshots alone may not resolve queue or impact.

## Cost gate before a directional trial

The [published base perpetual taker fee](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
is 4.5 bp per side: **9 bp for entry and exit before spread, market impact,
funding, and latency**. A taker reversal needs a delayed-entry gross move
larger than that total hurdle, not merely a statistically detectable
post-trade price reversal measured from the distressed fill. Any event-study
move measured from before the close includes pressure that occurred before
Rocket could react and cannot be counted as its executable return.

The cheapest meaningful next source gate is a **small, preselected archive
sample** that checks fill fields and event counts without looking at future
prices. First obtain object sizes and a transfer estimate with a signed
requester-pays account, then cap the sample and confirm its cost before
download. The subsequent economic gate would measure delayed post-block
mid-price movement and displayed spread/depth on the same fixed hours,
separately for voluntary loss closes and marked liquidations, with an
unconditional same-side control. If plausible gross reversal is below the
9 bp fee floor plus observed spread/impact, close the direction idea before
a full archive purchase. If it clears, freeze one causal rule and distinct
later-period replication before inspecting wider outcomes. There is
currently no basis to set the event threshold, horizon, or wallet cohort.

**Decision:** source feasibility is promising but unverified at the archive
level; economic feasibility is unknown. No FUT-010 experiment or production
change follows from this scout. The 2026 final holdout remains unread.
