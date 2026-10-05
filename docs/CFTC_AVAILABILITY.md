# CFTC receipt availability

The shared provider keeps the positions date separate from knowledge time.
Parsing a current report supplies no publication time. Direct HTTP acquisition
records the receipt only after the response and retains the exact response
SHA-256. OpenBB records the actual adapter receipt, even when a caller supplies
an earlier evaluation time.

Both BTC and ETH must have eligible knowledge time before directional context
is reported. A late receipt produces `LATE`; missing, malformed or timezone-free
receipt clocks produce `UNKNOWN`. Both suppress the regime as `unknown`.
Report-age staleness and market coverage remain separate checks. A legacy
`ProviderResult.retrieved_at` may provide a conservative observed receipt.

Observed current bytes are not reconstructed historical first-release vintages:
`historical_pit=false`, `historical_available_at=null`, `vintage_id=null`.
No Tuesday-to-Friday publication time is invented.

This focused correctness port credits the provider/receipt changes in
[#49 at 7c42582](https://github.com/jhonnyisaacc/rocket/tree/7c42582168e7538cfac00393bc3ffce54beb21b1)
and adds explicit suppression of UNKNOWN knowledge time. It does not merge the
momentum research runtime or accept its scientific foundation. Its synthetic
tests cover response/receipt ordering, source hashes, historical decisions,
post-receipt eligibility, invalid clocks and one late market.

The pinned
[FUT-005 lineage audit](https://github.com/jhonnyisaacc/rocket/blob/7c42582168e7538cfac00393bc3ffce54beb21b1/docs/research/momentum/CFTC_LINEAGE_AUDIT.md)
documents a separate annual-ZIP/+10-day/special-release path. That historical
failure and revised-vintage limitations remain evidence; this provider fix
neither reruns FUT-005 nor admits a COT/momentum successor. MOM-002 remains
unauthorized and unscored.
