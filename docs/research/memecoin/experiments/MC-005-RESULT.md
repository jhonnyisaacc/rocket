# MC-005 result — early net flow on a fresh ten-minute panel

Status: `CANDIDATE` for exit-risk association; `REJECTED` as a tradable entry rule. The [design](MC-005-FROZEN.md) fixed one net-buy-minus-sell score, cohort, clock, split, costs, zero-recovery stress and minimum gates before capture. The held-out **minimum gates passed**, but the stricter evidence needed for strategy promotion did not. Returns remain static-state hypothetical quotes, not fills.

## Acquisition and protocol gate

The read-only 600-second, 512 MiB-bounded session ended normally without collector errors. It received 152,392 log notifications and 251 create hints. All **152,120/152,120** signatures in fully observed interior slots matched 153 `getSignaturesForAddress` pages from `solana-rpc.publicnode.com`, a different host from the websocket source. First and last observed slots remain uncertified. The pinned IDL decoded 251 CreateEvents, 31,829 TradeEvents, five CompleteEvents and five Pump AMM migration events; four completion/migration pairs involved mints created inside this capture. All 15,223 supported new-mint state transitions reconciled.

The first quote audit reported 29 failures. Before running an economic result, the raw cases were classified: 17 sells had two lamports of gross output fully consumed by one protocol and one creator fee and therefore no positive cash exit; exact-input buys had up to one lamport of previously observed boundary rounding in each charged fee; one exact-input buy completed the curve, where the pinned exact-output calculation reproduced the event's SOL and token amount while the input approximation differed by 498 token base units. The original failed audit remains in the archive. The corrected audit records **23,910 supported quote validations, zero material failures**, 20 dust sells, 18 one-lamport protocol and 11 one-lamport creator-fee discrepancies, and one completion-cap case. No fee formula is claimed exact at these boundaries.

The whole-second block timestamp to receipt gap had median 1.547 seconds and p90 20.645 seconds across interior signatures. CreateEvent timestamp to receipt had median 1.419 seconds and p90 12.755 seconds; 37/251 creates exceeded five seconds and 28/251 exceeded ten seconds. Much of the delay clustered around 15:15 UTC. These clocks show when Rocket's observed features were actually available; the lag is too large to treat this session as uniformly fast early discovery. The original receipt-clock policy was retained without excluding slow names after outcomes were known.

Evidence: [`mc005-capture-20260924.tar.gz`](../data/mc005-capture-20260924.tar.gz), SHA-256 `59c272c5bf757c7d103ace545f5201625d3271f91a0911998f4ad0511934f368`. The 343,692,780-byte raw segment has SHA-256 `983a1433028b5b81c7d0c523dce62c562fc875461973c594aae26d33c7d5d1ea`. The archive includes the raw capture, manifest, all 153 second-provider index pages, failed and corrected audits, decoded observations, point-in-time snapshots, full universe and both result files. Extract to a new directory and run `python scripts/research/memecoin_audit.py DIRECTORY --offline --rpc-url https://solana-rpc.publicnode.com --max-pages 250`, then the base quote and MC-005 flow scripts. Audit, base and flow result files reproduced byte for byte.

## Frozen flow result

Of 251 creates, 110 met predeclared exclusions: 71 Mayhem, 24 non-native quote, 15 without a full 67-second covered window. The remaining **141** received a five-second score. There were 90 quoted exits, 34 unavailable curve exits, 15 missing as-of entry fee states and two unquoteable entries. The chronological split assigned 99 scored launches to development and 42 to evaluation. The top quartile used the frozen net buy-minus-sell count with create-signature tie breaking; scores had ties in both splits.

| Split / group | Scored | Entry known | Exit unavailable | Mean stress, 155k/leg | Mean stress, 1m/leg |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development, all | 99 | 82 | 20 | −31.55% | −44.49% |
| Development, top flow quartile | 25 | 25 | 1 | −21.71% | −35.40% |
| Evaluation, all | 42 | 42 | 14 | −33.35% | −46.15% |
| Evaluation, top flow quartile | 11 | 11 | 0 | +20.23% | +3.32% |

The top group's observed curve-exit unavailability was 1/25 in development versus 19/57 among its other entry-known names, and 0/11 in evaluation versus 14/31 among its other names. This is a distinct **risk association** worth independent replication. Zero failures among eleven held-out top names still allows a substantial underlying risk rate; it is not proof of safety. The 67-second curve sell check does not establish a viable alternate route or achieved liquidation.

The economic means are unstable. Development's top group was negative under both scenarios. In evaluation the top group had six positive quoted proxies under 155k/leg, but only three under 1m/leg; its adverse-fee median was **−8.36%**. One +288.65% modeled winner at 155k/leg drove the positive mean: removing it changes the held-out top mean to **−6.61%** at 155k/leg and **−21.46%** at 1m/leg. This leave-one-out check is descriptive, not a new selection policy. No inclusion, failed-entry rate, market response, priority-fee choice or actual exit balance delta for a hypothetical Rocket trade was measured.

## Decision and next falsifier

The predeclared minimum gates passed, which justifies further work on this **risk component**. They do not justify `ENTER`, a learned ranker, or a profitable net-flow strategy. Classify the economic result as `COST_DRAG` and `DATA_LIMITATION`/outlier-sensitive under the proxy, with `EXECUTION_UNREPRODUCIBLE` remaining for hypothetical orders. The independent risk association is a candidate, subject to new-window replication and participant/route accounting. Next acquire a separate covered cohort with measured receipt delays; test the unchanged risk definition, distinguish distinct buyers from repeated/cycling event users using transaction truth, and validate whether depleted curve liquidity has a viable alternate exit. Do not tune this panel's score, horizon or quartile cutoff.
