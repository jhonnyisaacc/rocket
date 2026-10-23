# MOM-DATA-003: proposed interval-based kline source contract

**Status: `PROPOSED_NOT_ACTIVATED`. No relaxed parser or alternative census
was run.** This is a source-contract finding after MOM-000 results, not a
replacement of its experiment. MOM-000 and the MOM-002 proposal inherit the
original ZIP vintage, nine excluded rows and exact population.

Exact vendor close=end-minus-one-unit is the usual formatting convention,
but is stronger than causal clock correctness requires. One anomalous bar
contains 1,980 BTC base volume and ends just 999ms before the ideal timestamp;
that discrepancy alone cannot prove its OHLC invalid. Conversely, metadata
that closes before its open is incoherent. The current archives cannot tell
whether an early close describes a last trade, a truncated interval, or an
interrupted market. See [actual anomalies](REPLICATION_REPORT.md).

A separately reviewed future source version should:

- Derive interval bounds from aligned `open_time` plus the declared 1h
  interval, using explicit spot/futures timestamp units. Record raw vendor
  close separately; do not let it advance knowledge or receipt clocks.
- Validate finite positive OHLC, OHLC containment, finite nonnegative volume,
  month/instrument identity and unique hourly opens. Separate absent slots,
  exact duplicate rows and conflicting duplicate revisions.
- Treat an in-interval nonideal close as a metadata anomaly, rather than
  automatic proof that its prices are invalid. Require independent evidence
  of interval completeness (source semantics or a separately acquired
  trade/alternate-bar reconstruction) before declaring the bar usable.
  Without that evidence retain UNKNOWN; no inferred last-trade explanation.
- Quarantine close-before-open, close-after-interval, malformed units or
  conflicting identities. Keep the complete raw row/hash/reason. Zero volume
  alone is not an invalidity rule: an independently verified no-trade interval
  can be valid, while an unexplained empty interval stays UNKNOWN.
- Stamp retrospective availability from a documented reconstruction policy
  and label it assumed; stamp prospective availability with actual receipt.
  Preserve source corrections as separate vintages, never overwrite bytes.

Activation requires independent review before using a different population
in any new inference. Review must specify completeness evidence and source
identity, not choose which bars to admit after observing their labels. A
future parser regression may validate formatting/completeness independently
of outcomes. It may not replace MOM-000, silently change the frozen MOM-002
population, or reopen MOM-001. No arbitrary timestamp-tolerance threshold is
chosen to admit a favorable result.
