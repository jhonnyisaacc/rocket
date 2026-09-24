# MC-003 result — independent exit-risk replication

Status: `REJECTED` as an entry basis; no strategy promotion, 2026-09-24. The [design](MC-003-FROZEN.md) fixed clocks, size, score, costs, population, chronological split and zero-recovery exit stress before this new 300-second cohort. Returns below are static-state quote proxies and scenario stress, not realized fills.

## Data gate and method correction

The read-only session received 38,968 notifications. Its 38,941/38,941 signatures in fully observed interior slots matched 40 `getSignaturesForAddress` pages queried from `solana-rpc.publicnode.com`, a different host from the websocket source. First and last observed slots remain uncertified. Pinned IDL decoding found 102 CreateEvents and 12,901 TradeEvents. Supported native, non-Mayhem new-mint state continuity passed 3,564/3,564 transitions; 8,712/8,712 supported trade quotes reconciled with zero material failures. One exact-input event had the previously observed unexplained one-lamport fee excess. Mayhem, non-native and dust cases remain outside that quote arithmetic.

The first parser pass recorded two `invalid bool` errors from another program's `Program data:` lines in transactions that also invoked Pump. Those lines had a colliding Anchor event discriminator. No economic result was run under that failed gate. The parser now follows each Solana log invocation stack and decodes data only while Pump is active. The corrected offline replay has **zero** decode errors; its 102 create and 12,901 trade counts match the earlier pass. This correction changes source attribution, not the frozen policy or observed Pump events.

Evidence: [`mc003-capture-20260924.tar.gz`](../data/mc003-capture-20260924.tar.gz), SHA-256 `b65788cc2d5de729394fedcdb0dd8264e9a879ae751955f12e00f8596ac81520`. It includes the raw 114 MiB segment, capture manifest, 40 second-provider index pages, audit, decoded observations, v2 PIT snapshots, complete universe and both results. The raw segment SHA-256 is `e5bc51be7bfe8d30a3e71634fedf8bc80c884d0d631d2a1e533c400fed61e663`. To replay after extraction, use `python scripts/research/memecoin_audit.py DIRECTORY --offline --rpc-url https://solana-rpc.publicnode.com --max-pages 60`, then run the baseline and risk scripts as in [HOW_TO_RUN](../HOW_TO_RUN.md). The URL in offline mode records the saved index's provider; no network request is made.

## Frozen outcomes

Of 102 creates, 50 met predeclared exclusions: 14 had no full 67-second observation window, 21 were Mayhem and 15 used a non-native quote. All **52** remaining launches received a five-second score. No entry fee state was missing. Twelve had an entry quote but no sellable exit quote, leaving **40** quoted returns. The chronological split assigned 37 scored names to development and 15 to evaluation.

| Split and population | Entry known | Exit feasible | Exit unavailable | Mean quoted return | Mean zero-recovery stress |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development, all scored | 37 | 29 | 8 | −12.90% (29) | −32.06% (37) |
| Development, top curve-progress quartile | 10 | 8 | 2 | −26.20% (8) | −41.26% (10) |
| Evaluation, all scored | 15 | 11 | 4 | −8.99% (11) | −33.67% (15) |
| Evaluation, top curve-progress quartile | 4 | 3 | 1 | −8.05% (3) | −31.42% (4) |

The held-out top quartile's quoted mean is slightly less negative than the held-out quoted universe, but is based on three names and remains negative. Under the predeclared zero-recovery stress it is also negative. Development's top quartile is worse than the full scored universe. This independent cohort does not replicate MC-002's tiny positive held-out quote subset and supplies no defensible entry edge. Zero recovery is a conservative scenario, not an observed liquidation value. All outcomes remain conditional on hypothetical entry and static historical states; actual inclusion, failure rates and market impact are unmeasured.

## Decision and next question

Reject this unmodified five-second curve-progress rank as an entry basis under the frozen cost scenario. Retain exit feasibility as a separate catastrophic-risk outcome: 12/52 eligible names lacked a sellable exit quote at the 67-second horizon. Do not fit a new cutoff to these same two cohorts. Next, collect longer prospective panels with transaction-level fee and balance deltas, inclusion/failed-entry evidence, exit-route coverage and prespecified survival/risk features. Test those features on fresh time windows before any `ENTER` decision is considered.
