# Point-in-time dataset contract

Status: design and offline validator, 2026-09-24. This is the data base for [MC-001](EXPERIMENT_LEDGER.md), not a claim that a training panel exists.

## Tables

1. **Raw event archive:** immutable bytes plus SHA-256, provider/request or websocket subscription, receive clock, slot, signature, instruction order, decoding status, protocol version and capture gaps. Keep failed transactions and missing pages.
2. **Observation table:** chain plus mint, event kind/stage, source ref/hash, event/block time, **actual available-at time**, decoded field/value, decoder and fee version. Preserve account slot and token/quote mint. A backfilled historical RPC read's availability is the retrieval time.
3. **Decision snapshot:** one token and decision time, observed stage and source, accepted numeric features with per-feature provenance. `build_snapshot` rejects missing/late clocks, duplicate fields, nonfinite numbers and outcome-named features. Snapshot fingerprint excludes later labels.
4. **Outcome table:** separate protocol completion and migration truth, collapse/rug definition, execution opportunity, forward cash outcome and censoring/coverage. Join only after snapshots are frozen. Label definitions and horizon are versioned.
5. **Universe ledger:** every observed create, missing decode, candidate, rejection and no-trade row. Track source uptime and independent completeness comparison; avoid survivor-only cohorts.

## Required checks before modeling

Replay identical raw bytes to identical snapshots; assert `event_time ≤ available_at ≤ decision_time` for every feature. Record source clock skew and provider delay distributions. Compare create signatures with an independent index for the same frozen window. Verify pool/curve accounts against the contemporaneous IDL and quote mint. Audit at least a sample of economic buys from signed transactions. Keep post-decision outcomes physically separate during feature generation. Split by calendar time and mint, with embargo when labels overlap. Refuse to calculate economic metrics when entry or exit state coverage is absent.

The builder is deliberately offline and accepts only independently decoded, sourced observations. Rocket's existing spool receipt establishes availability of bytes, not correctness of decoded fields or complete market coverage.

Snapshot schema v2 includes `quote_mint` in the fingerprint. MC-002's archived v1 rows appended that field after hashing; they remain available as historical evidence. The correction changes row hashes, not MC-002's numeric features or returns.
