# Continuation: recovered state, complete windows, one corroborated wallet

Status: **NO_EDGE_VALIDATED**. Research only, on `feat/cryptofutures_v3`. Automation remains **PAUSED**; no trades, alerts, persistent collectors or production changes.

## Outcomes

| Work item | Result |
|---|---|
| Truncated calibration event | Recovered from cached self-CPI instruction data; no new Helius request |
| Historical native-curve validation | 193 fills reproduce; 191/191 independent adjacent checks pass |
| Frozen follower pilot | Still six conditional simulations and twelve entry rejections; no return improved |
| Existing CATE windows | Both complete by provider-reported cursor exhaustion; 1,231 unique records, 389 failed |
| New social-wallet evidence | GMannnnn corroborated to one signer through two distinct fills; third supporting amount reconciliation |
| Unipcs five-minute activity | 119 records; one verified buy, not 119 trades |
| Next experiment | Frozen for September 13 UTC; no new development or holdout outcomes acquired |
| Regression suite | 75 tests pass, including offline reproduction |
| New Helius usage | 160 successful-response estimated credits; 180 conservatively reserved; actual billing unobserved |

The session began at **19:04:45 UTC**, with a 20:04:45 hard deadline and 19:54:45 acquisition cutoff. Exact completion time and elapsed duration are recorded in [session_completion.json](data/session-2026-09-21-continuation/session_completion.json). Work completed within the one-hour ceiling; it did not require spending the entire credit allowance or running for a full hour.

## 1. State recovery without relaxing execution rules

Recovered signature:

`335cgm4nVceZ7h34CtcL9ZbAK1zB16pBSkeqq6mLhkGj8d7Fg4ThgZZGs7fU3z51apyaUcz31owmjP85ni4UrEQ8`

The archived transaction has truncated logs but intact Pump self-CPI event bytes at outer instruction 3, inner instruction 36, stack depth 4. The event is nested under the sole selected trade at inner instruction 29. Program, event authority, historical layout, native quote, instruction amounts and actual reserve balance changes agree. The recovered event describes a 74,316,308-lamport curve input and 626,426,033,146 raw tokens. Protocol/buyback destination checks pass; cashback is claimed in the transaction and is not treated as an additional refund in the follower model.

Both previous→recovered and recovered→next independent state/quote checks pass. These neighbors occur in different slots, so slot order resolves their relative ordering; same-slot checks elsewhere still use cached block evidence. Cursor-complete adjacent coverage is required. The original strict decoder continues rejecting truncated logs by default; recovery is opt-in and scoped to this one signature.

Anchor documents instruction-embedded events as an alternative to potentially truncated logs. The event prefix is checked against fixed-revision source, and the payload retains the previously pinned May-18 Pump layout. These are compatibility checks, not a deployed-program binary attestation. [Anchor event documentation](https://www.anchor-lang.com/docs/features/events) · [Pinned event tag source](https://github.com/otter-sec/anchor/blob/62865c636aecc6974fc9cfebfc6cf08ca4f0bb72/lang/src/event.rs)

The winning fixture now has supported exit-state coverage at all frozen horizons. **Its nine entry scenarios still reject the 2% slippage floor**, so no winning-fixture return is reported. The primary losing scenario remains **−0.045596413 SOL** on a 0.1 SOL trade budget after median observed costs, with its locked deposit shown separately. These are known-outcome development fixtures and historical-state approximations, not untouched validation or executable profit claims.

Evidence: [recovery_result.json](data/session-2026-09-21-continuation/recovery_result.json), [before/after replay](data/session-2026-09-21-continuation/pilot_results.json).

## 2. CATE: the missing seconds mattered

Completed the exact existing inferred UTC windows, without widening them or substituting profiles:

| UTC interval, September 21 | Total unique records | Failed | New successful pages |
|---|---:|---:|---:|
| 18:23:00–18:24:00 | 541 | 166 | 6 |
| 18:24:00–18:25:00 | 690 | 223 | 7 |

The original captures ended at 18:23:11 and 18:24:09. The important new candidate fills occur at **18:23:28, 18:23:57 and 18:24:39**, outside that original coverage. Short final pages still returned cursors; separate empty terminal pages established provider-reported exhaustion. Failure rows and duplicate checks remain in the evidence.

Public profile: [GMannnnn on Fomo](https://fomo.family/profile/GMannnnn).

Corroborated signer:

`FPLXEqws2rKy4k8B2tARTGV632fYCnPqxEktVMKfJ2H9`

| Chain UTC time | Fomo displayed buy | Total owner USDC debit | Reconciled routed input | Separate quote amounts | Admission use |
|---|---:|---:|---:|---:|---|
| 18:23:28 | $5,530.57 | 5,555.000000 | 5,530.574000 | 24.426000 | First complete match |
| 18:23:57 | $5,530.03 | 5,555.000000 | 5,530.029499 | 24.970501 | Second complete match |
| 18:24:39 | $9,956.03 | 10,000.000000 | 9,956.028800 | 43.971200 | Supporting only: logs truncated |

The signer receives 59,403.380080, 59,186.426653 and 105,271.465038 CATE respectively. These quantities are on-chain findings; Fomo did **not** expose public fill quantities, and they are not falsely counted as independently matched UI fields.

The first two routed input amounts each have exactly one matching signer/transaction among the complete frozen windows, after requiring a CATE credit and USDC debit. Neither a shared fee payer nor common funding is used as identity proof. The earlier 5,000-USDC candidate remains excluded.

### Timezone verification and limits

The initial public-evidence record deliberately retains `timezone_verified: false`. A subsequent independent UI check pairs absolute and relative times for five public fills with UTC clock readings, without using chain times to select the offset. For example, the UI's 4:15 PM fill appears one minute old at 19:16 UTC; the selected 3:23/3:24 PM fills appear 53/52 minutes old. Only UTC−3 is consistent among the quarter-hour offsets tested, allowing two minutes for rounding and refresh. See [time evidence](data/session-2026-09-21-continuation/fomo_time_evidence.json).

That corroborates the frozen offset at minute precision, not browser configuration or exact fill seconds. Two complete transaction-level matches therefore satisfy the research admission rule. This remains a corroborated profile→wallet association, **not** proof of legal identity, sole wallet ownership, insider access, trader consistency or profitability. The displayed dollar amounts numerically match rounded USDC quantities; no independent historical USDC/USD oracle is asserted. Separate recipient roles remain fee-like, not provider-verified labels. The third transaction is not needed to meet the two-fill rule.

Rochaboyyyy and therear66 remain unchanged, with their previous missing-link and unsupported-chain limitations. No replacement candidates were selected. Identity discovery happened today; historical `available_at` remains null.

Evidence: [full identity adjudication and competitors](data/session-2026-09-21-continuation/cate_identity_adjudication.json), [coverage](data/session-2026-09-21-continuation/cate_resumed_coverage.json).

## 3. Unipcs: receipts are not entries

Used the already corroborated wallet `2heJbC32Tpfcb3nbUb5ER61K11FGZVfVGtVnDm6LDogF`, separate from the anonymous calibration wallet and new GMannnnn candidate.

The frozen interval is **August 30, 14:58:52–15:03:52 UTC**, centered ±150 seconds on the verified buy. One wallet-and-owned-token-account query chain, with `status:any` and `tokenAccounts:all`, returned 119 unique transactions across three pages, including terminal exhaustion.

| Classification | Records |
|---|---:|
| Verified USELESS buy | 1 |
| Incoming transfers, not established buys | 111 |
| Outgoing transfer, not established sale | 1 |
| Related-account failed attempts | 5 |
| No owner token change | 1 |

The outgoing transfer is 50,000 USDC. It is separate from the subsequent 50,000-USDC buy and cannot be counted as another investment or a realized trading loss. Incoming receipts include USDC and an unrelated token; no strategy revenue claim is made.

The verified buy spends **50,000 USDC total**, comprising **49,977.50 routed input + 22.50 separate fee-like transfers**. The 22.50 is already inside the 50,000 debit, not an additional charge. Received USELESS: **755,233.667715**.

All referenced transaction fees total 0.048735405 SOL, but **none is charged to this owner's native balance as fee payer**. Deducting those other-payer fees from the wallet would be incorrect. Off-chain reimbursements remain unknown.

The buy's transient WSOL account receives 2,039,280 lamports in creation funding, ends with zero balance, and explicitly closes to the owner. Wrapped principal inflows and outflows balance exactly; account conservation reconstructs the observed 2,039,280-lamport closure proceeds. The owner transfers the same amount back to the creation payer, explaining the original parser residual and leaving zero native cash change. This is an observed within-transaction refund, not an assumed future rent refund or profit.

This remains a five-minute activity ledger, not full portfolio accounting, realized PnL, zero-opening-inventory evidence or an AMM follower simulation. [Activity ledger](data/session-2026-09-21-continuation/unipcs_activity_ledger.json)

## 4. Spending, safeguards and reproduction

The published Helius full-history price is 10 credits per 100 returned transactions, rounded up, with a 10-credit minimum. We retained 100-record pages. [Helius historical API pricing and token-account filters](https://www.helius.dev/docs/rpc/gettransactionsforaddress) · [Credit documentation](https://www.helius.dev/docs/billing/credits)

- CATE: 13 successful requests, estimated 130 credits; 150 reserved including two failed local attempts.
- Unipcs: 3 successful requests, estimated 30 credits.
- Total: **160 successful-response estimate / 180 reserved / 1,000 cap**. No gap or contingency allocation used. Provider billing was not inspected.
- 1,150 records returned in new captures: 1,031 additional CATE records and 119 wallet-window records. One wallet-window transaction was already present in the earlier named cache: **1,149 transaction signatures are new to the baseline archive**. The overlapping source capture is intentionally retained because it establishes broader wallet/ATA coverage.
- Both initial CATE attempts encountered sandbox DNS failure. A read-only DNS check succeeded outside the sandbox; one explicitly documented retry per affected request then succeeded. Prior reservations were retained. No automatic retry loop or cap increase.
- Capture now requires explicit bounded session configuration for dispatch, applies closure/deadline checks to every session directory, fsyncs reservations before dispatch, and can reuse read-only captures from the previous session at zero request cost.
- Prior raw responses, manifests, ledgers, completion markers and derived session outputs are preserved and checked against baseline hashes. New outputs reference capture hashes and decoder versions. Credentials are not stored in research artifacts.

Reproduce without network access:

```sh
python3 /Users/jhonny/rocket/docs/research/memecoin/continuation_report.py --verify-only
```

The audit blocks network access, compares deterministic outputs and runs all tests. The baseline decoder still reproduces its original strict results; the continuation invokes scoped recovery explicitly. New tests cover malformed/duplicate/conflicting events, adjacent state failure, immutable cross-session cache reuse, closed sessions, deadlines, budget guards, bounded manual transport recovery, incomplete/repeated pagination, conflicting signatures, failed-attempt fees, identity competitors/time uncertainty, and observed versus invented refunds.

## 5. Next executable experiment

The baseline cache's latest transaction for the anonymous source wallet is **September 12, 08:14:30 UTC**. The next complete UTC day is therefore **September 13, 00:00–September 14, 00:00 UTC**, not another hand-picked winning period.

[Frozen next experiment](data/session-2026-09-21-continuation/next_experiment.json) specifies the first 20 qualifying native-SOL Pump buy events, development events 1–10 and untouched holdout events 11–20. Known calibration mints are excluded; unsupported execution, missing state, migration and failed simulated fills are preserved rather than replaced. Ambiguous source ordering blocks claiming a complete first-20 sample. The original size, delay, exit and slippage settings remain fixed. Repeated tokens and overlapping scenarios are dependent observations, not independent statistical samples or a funded portfolio.

No outcomes for this experiment were acquired in this session. The next research session should freeze its acquisition budget and complete source-event selection before gathering development execution states; holdout market outcomes must remain uninspected. A bounded genuine trade history for the newly corroborated GMannnnn wallet is a separate follow-up, not evidence that it is profitable. Matched controls and broader validation are still required before any wallet-selection edge claim.
