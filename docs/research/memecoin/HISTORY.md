# Historical evidence and authority

This index preserves the useful work without merging #27's roughly gigabyte-scale raw archive or copying #30's snapshot artifacts into the canonical PR. Those branches remain inspectable by commit. Historical documents and their roadmaps are **non-authoritative for current direction**; use the Constitution, Pillar and current Frontier.

| Source | Evidence to retain | Where to inspect |
| --- | --- | --- |
| PR #27, follower/wallet work | Bounded Helius acquisition and immutable hashes; instruction-level curve fee and reserve replay; one costed losing fixture and entry-rejected winner; signer/cashflow audit of wallet receipts; unresolved general expectancy. | `d01d865`, especially `docs/research/memecoin/2026-09-21-follower-replay-pilot.md`, `2026-09-21-continuation-report.md` and their manifests/tests. |
| PR #30, radar/intake | Public intake, Helius mint/pool reads, bounded spool, explicit no-edge decision labels, vault vs market-cap distinction, held-out label persistence and pool-vault holder semantics. | `9804d6c`, especially `artifacts/memecoin_radar/PR30_AUDIT.md`, `PHASE_D_HELDOUT.md`, `PHASE_D_HOLDER_CHECK.md`, and `rocket/workflows/memecoin_radar.py`. |
| Current main | Durable raw capture and caller-supplied PIT `collect/scan/evaluate/status`; no launch stream or validated edge. | `rocket/capture/spool.py`, `rocket/workflows/memecoin.py`, `docs/issues/02-memecoin-strategy.md`. |

The #27 and #30 branches contain more detail than this ledger; retain them as source evidence, not as two competing active research programs. The #30 `ROADMAP.md` and #27 frozen “next experiment” are historical proposals. Any continuation must be justified by the current Frontier. A future code port should be selective and independently tested against the current protocol version.
