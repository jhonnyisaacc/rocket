# MC-002 frozen design — earliest native-curve quote baseline

Frozen before the longer prospective capture. Parent: MC-001 stream/decoder gate. This is a **cheap economic falsifier**, not an executable return claim or strategy promotion.

## Question and mechanism

Among newly created, native-SOL, non-Mayhem Pump coins, does curve progress observed five seconds after the create notification rank later **costed quote-proxy** outcomes above an age-only/random eligible baseline? Early net buying can move the curve; that movement might predict further demand, but costs and reversal can erase it.

## Acquisition and population

Run one 180-second read-only `logsSubscribe` session on the official Pump program with a 256 MiB raw-segment bound. Preserve all successful/failing notifications, RPC responses, hashes and clocks. Independently reconcile signatures using `getSignaturesForAddress`. Admit only creates in fully covered inner slots, with a full 67 seconds of subsequent covered stream. Keep excluded, late, undecodable, Mayhem, non-native and no-trade rows in the universe ledger. Do not replace them with later winners. If the index or event decoder has gaps, stop economic evaluation and report the coverage failure.

## Frozen features at t0 + 5 seconds

`t0` is the wall-clock receipt of the successful `CreateEvent` log. A byte is available at its recorded receipt time, not its block timestamp. At t0+5s, use only same-mint Create/Trade events received by then. The baseline score is **curve progress**: `(initial_real_token_reserves - latest_real_token_reserves) / initial_real_token_reserves`, descending. Record observed buy/sell counts and reserve state as descriptive candidate features, but do not tune a combined score in this experiment. Use the last received trade event's state, with its source signature and hash. A full IDL match and valid quote mint are required. No future outcome can enter feature generation.

## Frozen outcome approximation

Model a 0.01 SOL buy at t0+7s from the latest eligible observed curve state, then a sell at t0+67s from the latest eligible observed state. Require a prior trade event to supply the as-of protocol and creator fee rates; charge both rates on each side, using the integer quote formulas validated against MC-001 native non-Mayhem fills. Do not charge buyback/holder-reward allocations again. Reduce entry tokens and exit cash by 2% each as a declared adverse slippage stress; charge 155,000 lamports network cost per leg, a historical scenario assumption from #27 rather than a measured quote in this cohort. Include size impact in each curve quote. If an entry is impossible, classify it as no-fill; if exit liquidity or stream coverage is missing, censor the return. Do not impute a profitable exit or force a terminal mark from a later read.

This is a **static-state counterfactual quote**, not a guaranteed included transaction. It does not propagate our hypothetical order through subsequent traders, model MEV or prove the 2-second latency can be achieved. A positive proxy only justifies stricter execution and prospective shadow work.

## Evaluation and falsifier

Chronologically split qualifying creates 70% development / 30% untouched evaluation, sorting by create receipt and signature. No score fitting or threshold search. In each split report full-universe counts, censoring, no-fills, net quote-proxy distribution and top-quartile versus all-eligible mean/median. Report the final 30% once. Negative or unstable held-out incremental expectancy rejects this simple progress factor as an entry basis. A too-small or heavily censored cohort remains inconclusive, not a reason to optimize the cutoff. Preserve all material trials and update the Frontier.
