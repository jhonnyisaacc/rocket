# MC-011 result — early trade actor and route calibration

Status: **accepted as bounded transaction-accounting evidence**, not as a new strategy feature or economic holdout. The deterministic [selection](../data/mc011-selection-20260924.json) was committed as `aac0693` before any MC-011 transaction fetch. The source was MC-010's already evaluated ten-minute panel, so no result here can validate a new entry rank.

## Population, retrieval and identity

MC-010 had 238 strictly create-verified fast scored mints. Their original five-second receive windows contained 2,201 unique trade signatures; 44 had multiple decoded Pump trades and were excluded from single-event balance attribution. The eligible single-event populations were 1,185 top-quartile buys, 388 rest buys, 415 top sells and 169 rest sells. Hash ordering chose 48/48/24/24 signatures without consulting exit outcomes. All **144/144** selected `getTransaction` responses were saved from independent publicnode RPC, with request/receive clocks, and all matched the observed signature and slot with successful metadata. These are later truth checks, not features available at the original five-second decision.

An event-sized token-account delta uniquely identified an owner in **142/144** transactions. The two ambiguous cases were rest-group buys: the saved pre/post metadata showed the curve account losing the event amount but no account gaining that amount. They remain `AMBIGUOUS_OWNER`; their event user is not imputed as an owner. In all 142 identified cases, the token-account owner matched `TradeEvent.user`; the pooled exact 95% match interval is **97.44–100%**. MC-004's independently observed routed-sell mismatch remains a counterexample to a universal shortcut.

| Stratum | Owner identified / selected | User = owner among identified | Other top-level route / selected | Median whole-transaction fee |
| --- | ---: | ---: | ---: | ---: |
| Top buy | 48/48 | 48/48 | 21/48 | 55,188 lamports |
| Rest buy | 46/48 | 46/46 | 9/48 | 31,211 lamports |
| Top sell | 24/24 | 24/24 | 11/24 | 110,734.5 lamports |
| Rest sell | 24/24 | 24/24 | 3/24 | 89,000 lamports |

The stratum-specific exact 95% lower match bounds are 92.60%, 92.29%, 85.75% and 85.75%. **44/144** transactions entered Pump through another top-level program, including 32/72 selected top-group transactions; a matching event user did not make their route a direct Pump call. All 142 identified owners were signer keys, while the fee payer matched the owner in 141/142. Whole-transaction fees exceeded 155,000 lamports in 47/144 and 1,000,000 lamports in 28/144. These are observed payer fees for other people's transactions, not hypothetical Rocket order costs or evidence that one flat fee applies to every route.

## Interpretation and reproduction

The hash-stratified sample supports a **high owner-agreement rate in these single-event early trades**, with explicit uncertainty and ambiguous records. It does not prove independent beneficial control: coordinated signers, common funders and same-slot round trips were not resolved. It also does not validate event-user count as a point-in-time wallet-quality feature, because its signed-account check was retrieved later. The top/rest route proportions are descriptive selection-conditioned counts and were not a frozen risk or return test. MC-010's negative costed returns and `NO_EDGE_VALIDATED` status are unchanged.

The [evidence archive](../data/mc011-actor-audit-20260924.tar.gz), SHA-256 `edd82a6033411784383b223913076fc046c1dd18fede758bc07d76f9cffd6c06`, holds the committed selection, 144 response records and deterministic report. The report SHA-256 is `c0a412ecea60f0880dce324d353c04cad6b5011675df3f94a6a8537582495334`. Replaying the report from an extracted archive against the archived MC-010 source reproduced it byte for byte. Next, verify funding/control clusters and route-specific cashflows on a separately frozen panel if they can be observed by the decision clock; retain this sample only as semantic calibration. In parallel, continue the independent alternate-exit and executable-fill work.
