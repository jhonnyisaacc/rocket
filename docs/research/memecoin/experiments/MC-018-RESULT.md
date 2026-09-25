# MC-018 result — later alternate-pool listing triage on MC-017 exits

Status: **exploratory later-discovery diagnostic**, not a prospective route test or a new strategy holdout. The MC-017 capture and its direct curve/route results were already frozen and archived. This check reused MC-012's deterministic selection rule and queried the [DEX Screener token-pairs endpoint](https://docs.dexscreener.com/api/reference) about 38–48 minutes after the MC-017 creation receipts. It cannot establish pool availability, reserves or executable sell cash at receipt +67 seconds.

The selection took all 52 MC-017 baseline curve-exit-unavailable mints and 52 hash-selected baseline-quoted controls. All 52 unavailable mints independently matched MC-017's stricter direct account status `EXIT_UNAVAILABLE`. Among controls, 50 were direct `QUOTED`, one had unresolved creation identity and one had a stale account context. All four batched requests returned HTTP 200 with list bodies, between 2026-09-24 19:31:47.827 and 19:31:52.142 UTC. A returned list is a third-party listing snapshot, not a complete Solana venue index.

| Selected group | Mints | Pump curve listing | Canonical PumpSwap listing | Other pool lead |
| --- | ---: | ---: | ---: | ---: |
| Direct curve exit unavailable | 52 | 52 | 0 | 0 |
| Baseline-quoted controls | 52 | 51 | 1 | 0 |

The one control's listed PumpSwap address `4xhjKom7D17hQm5mASdT8AKGKSKedtY62CpapccNJvk7` equals the canonical PDA derived from its mint, `CW1mrqPVKs42MYWfiEePFcKasEzqXsS64rrLwF7kpump`. Its listed creation time, 18:50:49 UTC, follows that mint's frozen 18:47:38.162916 UTC exit. MC-012's generic probe counts every non-`pumpfun` `dexId` as an “other venue”; the new assessment correctly classifies this address as **canonical PumpSwap**, not a noncanonical rescue. The original MC-012 probe code and historical report remain unchanged for replay.

This later API sweep yields **no listed noncanonical lead** among the 52 depleted direct exits. It does not prove there was no alternate venue at the exit clock. The source's ability to list Pump curves for all 52 but no other pool, and its control's after-exit PumpSwap listing, gives no as-of reserve or execution truth. MC-017's same-bank null canonical pool observation remains the stronger bounded fact. Cash recovery stays unknown, and no stress return is relabeled.

The [evidence archive](../data/mc018-later-route-20260924.tar.xz) contains the exact MC-017 direct report, deterministic selection, four raw timestamped API replies, original MC-012-style probe report and corrected route assessment. Archive SHA-256 `1745d076619881cd76c14882a65f1f0dc4cdaf84b8a8c384644d779647b5c196`; corrected assessment SHA-256 `321067cab37a434ecc591a4b56251ca53359b149dbaee7a251fdaac395cb021c`. Re-run `memecoin_later_route_assess.py` on extracted files and compare the assessment hash.

Next falsifier: find an independently verifiable noncanonical pool at a frozen exit clock and read its vaults/fee state from the same bank, or keep alternate recovery unknown. In parallel, calibrate an actual reachable route's size-aware fee and simulated instruction outcome and distinguish simulation from landed Rocket inclusion. Do not run another economic feature holdout on the assumption that a later listing equals a usable exit.
