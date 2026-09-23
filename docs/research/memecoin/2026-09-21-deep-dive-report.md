# Early-buyer deep dive — research decision

Status: **NO_EDGE_VALIDATED**. Research only, on `feat/cryptofutures_v3`. Automation remains paused; no trades, signals, notifications or persistent collection were enabled. The separate September 13 experiment and both earlier closed sessions are preserved.

## Main result

We found recurring early buyers, but also a concrete reason that copying them can be too late. The highest-ranked anonymous wallet, `JCZXR5AQyxyerEWWLWCqefen3otCTgEx3W9sHm1LThcs`, bought two development tokens early and appeared again in the later sample. In that later token, **34%**, it bought at token age **8 seconds** and disposed of the same token amount at **12 seconds**. Hypothetical submissions delayed by 5, 15 or 30 seconds would all occur after that observed disposal. This is a timing finding, not a calculation of either trader's profit.

Twenty-four verified token creations were investigated, including quiet launches. Eight anonymous wallets were selected without using returns. Four new public Fomo profiles were retained, but none met the wallet-mapping standard. September execution regimes did not pass the existing model's compatibility gate, so **no follower return is reported**.

## Wallet shortlist and observed behavior

Full addresses, signatures, amounts and source captures are in [shortlist_final.json](data/session-2026-09-21-deep-dive/shortlist_final.json), [wallet_behavior.json](data/session-2026-09-21-deep-dive/wallet_behavior.json) and [holdout_wallet_behavior.json](data/session-2026-09-21-deep-dive/holdout_wallet_behavior.json).

| Anonymous wallet | Development evidence | Research interpretation |
|---|---|---|
| JCZXR5…1LThcs | Wholesome entry age 22s, same-amount disposal 24s; uuu first entry 11s, subsequent buys, disposal 80s | Recurs in later 34% at 8s/12s. Useful for timing observation; **not a 15-second copy signal**. |
| 2kdMB6…pjdvX | BBP first entry 11s, subsequent buys, disposal 70s; uuu entry 24s, subsequent buys, disposal 77s | Repeated accumulation, but only two development tokens and no observed later-panel trigger. Five-minute follower holding is much longer than these observed episodes. |
| 6fAV85…rYwQ8 | MORFIK entry 0s, same-amount disposal 10s | One token; source disposal precedes primary follower submission. |
| C5EMTG…KJyqw | Liberland entry 0s, same-amount disposal 3s | One token; holder-reward execution unsupported. |
| NULLio…7qZh | Liberland entry 0s, same-amount disposal 2s | Same limitations; agreement with another address is not proof of independence. |
| 5n2umv…YF4C4 | $TOAD entry 1s, same-amount disposal 110s | One observed episode, not evidence of consistency. |
| BUBBLE…hCg9 | zen entry 1s, same-amount disposal 3s | Too fast for all configured follower delays in this episode. |
| DnWZJD…MmXAu7 | zen entry 1s; no corroborated disposal in decoded curve events | Missing observed disposal is not proof of continued ownership or an available exit. |

“Disposal” above means signed, reconciled token movements. Sale cash proceeds were not generally validated; it does not mean profitable exit or complete inventory liquidation.

Public identities remain separate:

- **GMannnnn**, `FPLXEqws2rKy4k8B2tARTGV632fYCnPqxEktVMKfJ2H9`: prior two-fill corroboration retained. September 10–12 address/token-account coverage exhausted at 78 records: 29 buy-like, 8 sell-like, 35 receipts, 5 outgoing transfers and one unresolved activity. Buy/sell-like classifications are not promoted to independently verified AMM fills. Owner-paid network fees observed: zero; sponsorship is not free execution for a hypothetical follower.
- **Unipcs**, `2heJbC32Tpfcb3nbUb5ER61K11FGZVfVGtVnDm6LDogF`: prior corroboration retained. Token-account-inclusive query capped at 4,000 records, dominated by 3,474 receipts. A separately frozen direct-address diagnostic exhausted at 177 records, including 3 buy-like, 13 sell-like, 3 failed and 158 other records. The direct-address subset is complete; the all-token-account history is not. No full portfolio PnL.
- **Anonymous calibration wallet**, `789sBYAGntSyAPoS4ZH3zo3SUFuv1jeAjPeaq7muVany`: one non-buy record in the bounded dates; no social identity assigned.

Research usefulness is highest where identity and accounting coverage are strongest, not where displayed gains are largest. The four new feed-selected profiles—ballerboi, Onchainmetrics, NBA__trey and menalwaysregret—remain **unmapped**. The NBA__trey check captured 2,973 records in one fixed minute but did not reconcile the six displayed USD sale amounts to owner USDC credits; coverage remains capped and USD valuation is unresolved. This is not evidence that no matching transaction exists. See [public_panel.json](data/session-2026-09-21-deep-dive/public_panel.json).

The explicitly linked [X post](https://x.com/elonmusk/status/2101178647088410828) was inspected in the logged-in browser. Its public timestamp is September 19, 05:16:42 UTC. It concerns merchandise, not a purchase or wallet disclosure. It does not establish NBA__trey's X identity. No same-name accounts were guessed.

## Token panel and hypothesis scorecard

Development: FWIDGE, zen, BBP, $TOAD, VAR, BREADPITT, USMS, Liberland, Wholesome, JABAL, MORFIK and uuu. These are the proven first twelve eligible creations in the fixed September 14 window. All twelve fifteen-minute reserve histories exhausted; JABAL retains a truncated-log decoding gap. BREADPITT had no qualifying non-creator buyer and was retained.

Later sample: PAIDSEM, VRX, cardman, ghost, PMP, Census, 34%, PD, TOD, wind, .family and ZGhosti. Eleven activity intervals exhausted; **.family remains capped at 1,186 unique records**. VRX retains four decoding failures. Two earlier creation records were unresolved by the frozen decoder, so this is a **partial chronological panel**, not a proven complete first-twelve holdout.

Primary scenario: 0.1 SOL, 15-second submission delay, exit decision five minutes after entry, same exit delay, 2% tolerance. All 18 size/delay/horizon combinations per token/rule are retained in the machine-readable results; they are not independent observations. All rules were evaluated within the explicitly frozen first-five-minute observation scope. Fifteen-minute exits generally extend beyond captured evidence and are not invented.

| Rule | Development observed triggers | Later observed triggers | Matched ordinary controls, dev/later | Executable cases |
|---|---:|---:|---:|---:|
| Repeat early buyer | 7 | 1 | 2 / 1 | 0 |
| Two-wallet convergence | 3 | 0 | 0 / 0 | 0 |
| Absorption after decline | 1 | 0 | 0 / 0 | 0 |
| Momentum only | 3 | 4 | Not applicable | 0 |

Full primary classifications, including no-trigger and missing-evidence cases, are in [summary.json](data/session-2026-09-21-deep-dive/summary.json). Across the complete sensitivity matrices: development has 540 `no_trigger` and 324 `unavailable` rows; later sample has 648 `no_trigger` and 216 `unavailable`. There are zero simulated or slippage-rejected fills: the execution gate failed before slippage could be evaluated. Missing evidence is not counted as a no-trigger result. Unresolved routing can still conceal economic buyers, so no-trigger means no **verified observed** trigger.

No direct transfer between shortlisted pairs was found in the bounded reserve evidence, so flagged-pair exclusion does not change these observed counts. This narrow coverage cannot establish wallet independence. Common fee payers, routers and exchanges were not treated as common ownership.

## Execution gate and contradictions

The September 12 official Pump [IDL revision](https://github.com/pump-fun/pump-public-docs/tree/e0687ae9b7e064a0f54efc7297c65eecfbba3a8f) matches additional creation and trade fields absent from the older decoder. It supports decoding, not a blanket claim about deployed program semantics.

Diagnostic arithmetic produced 339 records where the formula and native reserve delta both matched, 16 formula matches without matching native reserve deltas, and 584 formula mismatches despite matching native deltas. Mayhem behavior, creator/holder-reward fees and native-versus-wrapped reserve handling remain outside the admitted regime. No fitted lamport correction or extra 50% buyback fee was introduced. Matching a trade's own reconstructed state is not independent replay validation.

Independent adjacent account checks found 1,331 matching observed native/base balance pairs and seven pairs with missing balance evidence. An initial audit incorrectly represented unreported token balances as zero; that audit is explicitly superseded by `development_independent_continuity_v2.json`, with a regression test. There are no observed mismatches in that corrected audit, but unknown wrapped balances and virtual-state/fee configuration still prevent execution admission.

Protocol charges, network inclusion, tips, account cash requirements, migration and exit liquidity must all be supported before a return can be computed. Deposits are not automatically expenses or assumed refunds. Here those unresolved components remain explicit null/unpriced fields. Historical block-time delays are hypothetical—not measured bot latency.

## Required chronological case studies

1. **First executable case: unavailable.** No selected case passed the September compatibility gate. A winning example was not substituted, and no leader-fill-price shortcut was reported as follower execution.
2. **First triggered execution failure: zen.** H1 and H2 appear at age 1s. Ordinary-buyer control is unmatched. One shortlisted buyer disposes of its observed acquired amount at age 3s. The fee/reserve regime is unsupported; this is `unavailable`, not a fabricated slippage rejection or loss.
3. **First non-triggering token: FWIDGE.** The complete bounded history contains ten decoded trade events, including protocol/infrastructure activity. Only one non-creator buy meets economic-owner and payment checks; its wallet is not shortlisted. None of the frozen rules triggers. Mayhem execution remains unsupported regardless.

Additional later-sample timing check: **34%** supplies the only recurring-wallet trigger, with an ordinary-buyer control available. The leader's observed buy-to-disposal interval is four seconds. At the primary delay, submission would be token age 23s, eleven seconds after its disposal. This undermines blind delayed following without proving a negative net return.

## Decision and next executable experiment

- **H1:** candidate only for prospective **timing and persistence observation**, not a buy signal. JCZXR5… recurs but exits quickly; 2kdMB6… merits observation of repeated accumulation, not an inferred profitable strategy. Any filtering on holding behavior would be a new, separately frozen hypothesis—not a rescue of this result.
- **H2/H3:** unsupported. There were no verified later-sample triggers, dependencies are incompletely observed, and execution is unavailable. Zero triggers in this small partial panel does not statistically falsify either idea.
- **No hypothesis has demonstrated an advantage over momentum or ordinary buyers.** No profitability claim was tested successfully because the necessary execution evidence failed its gate.

Next executable research step: validate one explicitly selected September non-Mayhem native-curve regime against independent balances, historical fee configuration and both quote directions; then use a **new untouched chronological token window** to test the locked wallet list and fixed rules. A prospective detection/leader-exit timing study can be specified separately, but no collector or notification system was started. The previously frozen September 13 experiment remains separate.

## Audit and reproduction

- **94 requests; 31,912 returned rows; 28,237 unique captured transaction signatures.** These are within-session counts, not all necessarily globally new transactions.
- **3,720 estimated successful-response credits**, versus **6,970 conservative reservations / 10,000 cap**. Actual provider billing was not observed. Estimates follow the [official history pricing](https://www.helius.dev/docs/rpc/gettransactionsforaddress), while reservations use the maximum possible page cost. No automatic retries or bucket transfers.
- Diagnosed contingency: 240 credits for separately frozen narrow holdout tails, 30 for a direct-address Unipcs query. Original query page caps and raw captures remain intact.
- **108 tests passed**, including the original 75. Cached reproduction re-decoded 1,144 holdout events, reproduced shortlist and results, verified the strategy lock and prior artifacts, and made **zero new network requests**.
- Three primary papers contributed concrete dependence, manipulation and selection-bias checks; see [literature.md](data/session-2026-09-21-deep-dive/literature.md). The `firecrawl-research-papers` skill was used.
- Acquisition ended early within the authorized three-hour maximum; unused credits are not a spending target. Exact closure time is recorded in the session completion marker.

Reproduce without network:

```sh
python3 docs/research/memecoin/deep_report.py --verify-only
python3 -m unittest discover -s docs/research/memecoin -p 'test_*.py'
```

Holdout integrity disclosure: the shortlist and core decoder/strategy hashes were locked before any holdout capture. A **post-lock coverage-only driver** then joined overlapping diagnosed tails, without changing those hashes or thresholds. This is disclosed rather than describing the whole pipeline as a pristine preregistered holdout. The later data have now been inspected and must not be reused as an untouched validation set. Current identity discovery is never represented as historically available.
