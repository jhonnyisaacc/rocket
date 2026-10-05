# MC-010 result — fast-receipt net flow on a signed, covered panel

Status: **rejected as an economic entry rule**. The prospectively frozen structural-quarantine and protocol data gates passed. The unchanged five-second net-flow score again separated modeled curve-exit availability, but both fee scenarios had negative costed stress returns in both temporal splits. No `ENTER` rule or live order path is authorized.

## Captured population and data gate

The read-only Solana Labs `confirmed` Pump log capture ran from 2026-09-24 16:32:37.794 UTC (subscription acknowledgment) through 16:42:37.826 UTC. Its 600-second duration bound ended normally, with 154,216 raw notifications, 154,588 frames, 304 MiB of raw JSONL, and no collector errors. The raw segment SHA-256 is `165ce24df402fc23bdd6231d3fd1ce766397b8b8c55bb3582527e7a5ce8a3f27`. The independent publicnode index required 155 saved pages and matched **154,144/154,144** valid signatures in fully observed interior slots. There were zero missing or extra valid signatures and zero structurally invalid notifications to quarantine in this window. First and last slots remain boundary exclusions.

The pinned IDL decoded 310 CreateEvents, 25,799 TradeEvents, four CompleteEvents and four CompletePumpAmmMigrationEvents. There were zero truncated successful logs, event decode errors, signed-create mismatches, or missing transaction order records. Native non-Mayhem state continuity passed 13,195 transitions with zero failures, and 21,309 supported trade quotes passed integer reconciliation with zero material failures. This establishes the specified **observed-window** data gate, not perpetual uptime or executable order inclusion.

All 310 creates remain in the universe. Their whole-second chain timestamp to receive age had median 1.3575 seconds and p90 1.764 seconds; none exceeded five seconds. These ages are a coarse screen, not network latency. The frozen quote baseline excluded 70 launches from analytic eligibility and scored 240; all 240 met the fast receipt screen. Later signed-transaction inspection verified 196 through captured top-level `create_v2` instructions and 42 through saved independent transaction responses. Two remained unresolved by that strict identity rule and were excluded, leaving **238** fast scored names. One unresolved transaction used two top-level Pump instructions; the other entered Pump through a different top-level program. This result does not infer identity from those event logs alone.

## Frozen risk and return test

The 238 verified names were re-split 70/30 by create receipt, with signature tie breaking, then ranked by the unchanged MC-005 score (`observed_buys_5s - observed_sells_5s`). The model used the frozen 10,000,000-lamport size, 7-second entry, 67-second curve exit, 200-bps slippage per leg, and 155,000/1,000,000-lamport network-fee scenarios per leg. Unavailable curve exits receive zero recovery **only in the stress model**. Unknown entry outcomes stay unknown.

| Split | Top quartile unavailable exits / known entries | Rest unavailable exits / known entries | Top stress mean, 155k fee | Top stress mean, 1m fee | Top quoted-only mean, 155k fee |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development (167 scored) | 7/42 (16.7%) | 35/88 (39.8%) | −33.56% | −46.35% | −19.97% (35) |
| Evaluation (71 scored) | 1/18 (5.6%) | 11/33 (33.3%) | −32.72% | −45.57% | −28.67% (17) |

The development and evaluation top-group exact 95% exit-unavailable intervals were 7.0–31.4% and 0.14–27.3%, respectively; the corresponding rest intervals were 29.5–50.8% and 18.0–51.8%. Descriptive one-sided Fisher probabilities for lower top risk were 0.00623 and 0.02418. These were not a frozen significance gate and do not establish independent buyers or causal protection. Development had 37 unknown outcomes among 167 scored; evaluation had 20 among 71. The held-out top stress mean after removing its best modeled winner was −38.93% at 155k and −51.31% at 1m.

The minimum evaluation sample gate passed (51 known entries, 18 top names), and top curve-exit unavailability was lower than the rest in both splits. The required positive costed top return in both splits and both fee scenarios failed, as did the held-out leave-best-out positive return. The risk association is a repeatable **candidate component** under this proxy; it is not an economic entry edge. Quoted-only returns were also negative. A curve-unavailable name may have another exit venue, so zero recovery cannot be presented as observed liquidation. Conversely, static-state quotes do not establish Rocket fills, priority-fee choice, market impact or route execution.

## Reproduction and next implication

The archive contains the raw bounded capture, manifest and checksum, all independent index pages, decoded observations, quote and flow rows, later transaction-response attempts and both frozen results. An offline replay of the saved index, baseline, flow, identity and fast-cohort scripts reproduced ten output-file SHA-256 hashes byte for byte. Archive path: `../data/mc010-fast-flow-20260924.tar.xz`; SHA-256 `704a48905b3dd0fb993f7dd44775d5642faa5da4a6cdf647f8e5199c59c924e7` (45 MiB).

Failure attribution: **`NO_ECONOMIC_SIGNAL`** for the unchanged rank under this costed quote proxy; **`EXECUTION_UNREPRODUCIBLE`** for actual entry/exit fills and alternate venues; **`IDENTITY_SCOPE`** for the two strict-create-unresolved names. The acquisition gate passed for this specific ten-minute window, while prior long-window latency bursts remain a reliability concern. Next work should measure beneficial buyer identity, alternate exit-route liquidity and actual transaction inclusion/fee distributions on covered panels, and benchmark an authenticated dedicated feed if available. Do not retune flow on MC-010 or promote it to Rocket decisions.
