# MC-006 result — flow-risk replication with receipt-delay gate

Status: `CANDIDATE` risk association retained for further testing; `REJECTED` as an actionable or profitable entry rule. The [design](MC-006-FROZEN.md) fixed the same flow score and economic policy as MC-005 before this independent 600-second capture. The new collector sync policy was an infrastructure change, not a feature or outcome retune.

## Capture and protocol gate

The read-only capture ended normally with 199,540 notifications in 199,868 raw frames. Its v2 manifest records 3,794 disk syncs for the bounded 396,600,408-byte segment, versus per-frame sync in MC-005. Eight create-transaction fetch attempts timed out; raw Pump events and their receipt clocks were preserved, and the later transaction identity remained unresolved where no response was captured. Of 272 decoded CreateEvents, 204 had corroborating fetched `create_v2` transactions with zero mint mismatches; 61 lacked a captured transaction response and seven did not meet the strict single top-level `create_v2` account check. Do not treat unresolved cases as transaction-confirmed identity.

The independent `solana-rpc.publicnode.com` signature index matched **199,403/199,403** signatures in fully observed interior slots across 200 pages. First and last slots remain uncertified. The pinned IDL decoded 272 CreateEvents, 28,732 TradeEvents, eleven CompleteEvents and eleven Pump AMM migration events with zero layout errors. Native non-Mayhem new-mint state transitions passed 11,050/11,050; 18,632 supported quotes passed with zero material failures. The audit separately counted three no-cash dust sells, twelve one-lamport protocol-fee boundaries, five one-lamport creator-fee boundaries and one exact-input completion-cap rounding case.

Evidence: [`mc006-capture-20260924.tar.xz`](../data/mc006-capture-20260924.tar.xz), SHA-256 `522325532a34a26f2104b04f61c6fb22c03c81f96a21deff57cad53e6b2ce87d`. Raw segment SHA-256 `a575afd7084818c708f9d84aa6a3cba8e8798460e214235072c0b41482dd999c`. The archive contains manifest, raw frames, all second-provider pages, audit, decoded observations, point-in-time snapshots, full universe, frozen quote and flow outcomes, and risk/latency/participant diagnostics. Extract it and run the audit offline with `--rpc-url https://solana-rpc.publicnode.com --max-pages 250`, then the base quote, flow and diagnostic scripts. Audit, base, flow and diagnostic result files reproduced byte for byte.

## Unchanged risk and economic results

Of 272 decoded creates, 271 were inside the covered interior. The baseline excluded 124 by its frozen regime/window rules, scored 147, and found 112 quoted exits, 32 unavailable curve exits and three unquoteable entries. The chronological split had 103 development and 44 evaluation scored launches.

| Split / group | Entry known | Curve exit unavailable | Exact 95% risk interval | Mean stress, 155k/leg | Mean stress, 1m/leg |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development top flow quartile | 26 | 4 (15.4%) | 4.4–34.9% | −25.46% | −38.87% |
| Development rest | 75 | 22 (29.3%) | 19.4–41.0% | — | — |
| Evaluation top flow quartile | 11 | 0 (0%) | 0–28.5% | −21.33% | −35.06% |
| Evaluation rest | 32 | 6 (18.8%) | 7.2–36.4% | — | — |

The top group had lower observed unavailable-exit rates in both splits, meeting the frozen **directional risk replication** requirement with 43 entry-known evaluation launches. Exact descriptive one-sided Fisher probabilities were 0.125 in development and 0.149 in evaluation; intervals are wide. The event-user diagnostic found median 15.5 distinct early buy-event addresses in the development top group versus two in the rest, and 20 versus three in evaluation. These are emitted addresses, not confirmed distinct beneficial buyers. The separate MC-004 transaction audit found a routed-sell counterexample to equating event user with token source owner.

Economic stress was negative in both splits and at both fee levels. The evaluation top group mean was **−21.33%** at 155k/leg and **−35.06%** at 1m/leg; its quoted-only mean at 155k/leg was also negative. This is an unchanged-policy failure to replicate MC-005's outlier-driven positive held-out mean. No entry edge is accepted.

## Latency and endpoint falsifier

CreateEvent timestamp-to-receipt median was 2.040 seconds, p90 **28.056 seconds**, with 118/272 above five seconds and 85/272 above ten seconds. Minute-level delay bursts reached 31.71-second p90 at 15:36 UTC and 43.29-second p90 at 15:39 UTC. These are integer-second event timestamp differences, not exact wire latency. The prespecified fast-discovery gate failed. Reducing disk sync frequency did **not** eliminate the delay, so per-frame sync alone cannot explain MC-005's burst. A post-result, non-selection diagnostic restricted to names received within five seconds found development top 2/14 versus rest 5/32 unavailable exits; this small subgroup does not establish fast-path risk improvement.

An eight-second test of a second public websocket host was independently indexed and rejected: it carried 405 of 871 interior signatures and missed 466, with a roughly 10.4-second median block-time-to-receipt gap. [Raw test and both audits](../data/alternate-ws-smoke-20260924.tar.gz), SHA-256 `a9ba34c42896335430d91c39906059d2cac6883890433e0d022de7034e26cf2f`, preserve the failed route. The initial audit stopped at the pre-subscription slot even though the websocket began 26 slots behind; the corrected audit pages back to the first observed slot and exposes the full missing-signature count. This endpoint is not an acceptable replacement for prospective early discovery.

## Decision and next step

Keep early net flow as an **unpromoted exit-risk candidate**: lower unavailable-exit rates appeared directionally in two prospective cohorts, but exact uncertainty is broad, receipt timing fails actionability, and profitability did not replicate. Do not change the score or top-quartile cutoff on these cohorts. The next bottleneck is a faster, independently covered early stream and transaction-level participant/exit-route truth. Evaluate a provider or ingestion path on simultaneous receive clocks and independent signature coverage before another strategy holdout; retain the full negative universe. Execution and `ENTER` decisions remain disabled.
