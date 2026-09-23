# Codex handoff — memecoin radar

As of 2026-09-23T15:10Z. Research infrastructure, not a strategy. Continue on the existing branch. Do not open a second pull request.

- Repo: https://github.com/jhonnyisaacc/rocket
- Pull request: https://github.com/jhonnyisaacc/rocket/pull/30
- Branch: `cursor/memecoin-radar-intake-f1ca`
- Operator: Jhonny Vergara
- Model for new work: Grok 4.7 high fast (`grok-4.7-high-fast`). Do not use Opus 5.5.

## Objective

Learn whether the observable Solana memecoin universe contains a repeatable point-in-time edge, and what evidence would support it.

The current liquidity floor, age window, WATCH gates, ranking, and feature set are a frozen baseline. They are not presumed to belong in an eventual strategy. Do not retune them to manufacture `WATCH_ENTER` rows.

Every JSON result keeps `edge=NO_EDGE_VALIDATED` and `execution_enabled=false`. A `WATCH_ENTER` row is not a buy. `NO_EDGE_VALIDATED` is an allowed conclusion. Human-gated. Read-only. Identification is not an entry. Browser and X are evidence sources, not execution.

Ignore futures, Hyperliquid, and `rocket/workflows/crypto.py`. PR https://github.com/jhonnyisaacc/rocket/pull/27 is research history. Do not merge it and do not commit its dump.

`HELIUS_API_KEY` is the only Helius env name. It is a Cloud Agent runtime secret and is also set on the operator's computer. Never print it. Never write it into files, JSON, commits, logs, or chat. Strip any URL that contains `api-key=`.

## Where the work stopped

Phase A, Phase B, and Phase C are written. Phase D challenged one claim. The other Phase D claims are still open, and the clock is now long enough to test them. Phase E is forbidden until a hypothesis survives a held-out test. None has.

Only the lowest unfinished phase may be worked. If new evidence shows the direction is wrong, say so and change the next phase before writing more code.

## What the code already does

Commands, all read-only, one JSON object each when used as documented:

- `rocket memecoin collect --json`
- `rocket memecoin scan --json`
- `rocket memecoin radar --json` (collect, then scan)
- `rocket memecoin status --json`

Logic lives in `rocket/workflows/memecoin_radar.py`. `rocket/cli.py` only wires the commands. `rocket/workflows/memecoin.py` still scores old caller PIT fixtures (`features`, `contract_address`) when `scan --input` is that shape. Empty caller fixtures are `CALLER_STATE_MISSING`. A missing live feed is `DATA_UNAVAILABLE` or `INSUFFICIENT_EVIDENCE`, not “no memecoins exist.”

Intake, in order:

1. Graduated pump.fun coins from the page’s own client: `GET https://frontend-api-v3.pump.fun/coins?complete=true`. The explore board does not print mints. `fomo.family` is login-walled.
2. `GET https://pump.family/api/sales`. Phase `migrated` is in universe. Phase `launched` is still on the curve and cannot be `WATCH_ENTER` (cap 8). Phase `open` is excluded. The provider name stays `browser:fomo.family`.
3. Helius, only when `HELIUS_API_KEY` is set: `getAccountInfo` on the mint, pool account when present, `getTokenAccountBalance` on the PumpSwap quote vault, `getTokenLargestAccounts`. No `getTransactionsForAddress`.
4. X is optional and was not consulted. `social_heat` stays `unknown`. No tweet creates a mint.

Liquidity is `2 × current quote-vault balance × snapshot SOL price` (`solUsd` from pump.family). Graduation-time `real_quote_reserves` (about 85 SOL, the same print on coin after coin) is not liquidity. A missing or zero vault is `liquidity_usd: null` and the row is `SKIP`. Advertised market cap is not liquidity.

Frozen gates, do not change them in passing:

- Liquidity floor: $10,000 (`LIQUIDITY_FLOOR_USD`)
- Age floor: 30 minutes (`AGE_FLOOR_SECONDS = 1800`)
- `WATCH_ENTER` also needs `solana:mainnet`, a valid mint, PIT-legal clocks, graduation `graduated`, window `closed`, and a Helius mint confirm. Reason on that label is `floors_met_not_an_entry`.
- `TOO_EARLY`: Helius confirmed the mint and age is under 30 minutes.
- `AVOID`: confirmed mint that fails a hard gate other than age, including liquidity present and under the floor.
- `SKIP`: a required check cannot be computed. `SKIP` is not “safe.”
- Selected cap 20. Intake cap 40, preferring ages 30 minutes to 24 hours. Newest first, then liquidity.
- Exit 0 includes zero `WATCH_ENTER`. Exit 2 is provider down. Exit 1 is bad config.

`top1_holder_bps` is the largest token account’s share of supply. `dev_hold` stays `UNKNOWN`. Phase D showed that on the 12:08Z selected set this largest account is the pool base vault, not a dev and not a bundle. Do not treat holder share as a feature until that is checked on any new cohort.

Cron, a Grok bot, Discord, and “run radar every 5 minutes” are quarantined in `artifacts/memecoin_radar/HOW_TO_RUN.md` under `LATER_NOT_NOW`. Do not install crontab. Do not add a scheduler. Do not wire a bot.

## Evidence already on the branch

Read these before changing anything. Paths are on `cursor/memecoin-radar-intake-f1ca`.

- `artifacts/memecoin_radar/PR30_AUDIT.md` — what is measured, what is only a proxy, what is unvalidated.
- `artifacts/memecoin_radar/ROADMAP.md` — phases A–E and the stop rule.
- `artifacts/memecoin_radar/HOW_TO_RUN.md` — commands. Scheduling is under `LATER_NOT_NOW`.
- `artifacts/memecoin_radar/RADAR_CONTRACT_v0.md` and `DECISION_CONTRACT_v0.md` — frozen label rules, not a strategy.
- `artifacts/memecoin_radar/LIVE_CONFIRM.md` and `LIVE_CLOUD.json` — baseline scan.
- `artifacts/memecoin_radar/PHASE_B_UNIVERSE.md` and `PHASE_B_SCAN.json` — distributions, 3.5h reprice, DexScreener comparison.
- `artifacts/memecoin_radar/PHASE_C_HYPOTHESES.md` — five falsifiable claims. None is an edge.
- `artifacts/memecoin_radar/PHASE_D_HOLDER_CHECK.md` — top-holder identity.
- `artifacts/memecoin_radar/FINDINGS.md` and `browser_pass_2026-09-23T0715Z.md` — why scan could not discover tokens before this branch, and the first browser pass. Boards were mint-less or login-walled. Mints came from the public JSON those pages already call.

### Baseline scan, 2026-09-23T08:38:52Z

Selected 20. `WATCH_ENTER` 0, `SKIP` 1 (VSOF, no page pool), `TOO_EARLY` 0, `AVOID` 19 for `liquidity_below_floor`. Vault liquidity about $2.62–$991.65. Helius `HEALTHY`. Coverage `OBSERVED`. The feed was not empty. Research status `INSUFFICIENT_EVIDENCE`.

### Later scan, 2026-09-23T12:08:10Z

Selected 20, a different cohort. None of the baseline 20 were in this set.

- `WATCH_ENTER` 2: BONNIE `liquidity_usd` 11252.17, age 3052s; CHICKEN `liquidity_usd` 10356.06, age 3376s. Reason `floors_met_not_an_entry`. Not a buy. Not repriced since.
- `SKIP` 2: burrito (Helius confirm missing), doge (`liquidity_unknown`).
- `AVOID` 16. `TOO_EARLY` 0.
- `liquidity_usd` on finite rows: n=18, min 4.23, p25 63.15, p50 265.75, p75 826.88, p90 3969.08, max 11252.17. Sixteen of the finite prints were at or below 1231.80.
- `age_seconds`: n=20, min 2030, p50 3105, max 3771.
- `top1_holder_bps`: n=19, min 1983, p50 9650, max 9987.

### Baseline 20, reread at 2026-09-23T12:10:13Z

3 hours 31 minutes later. All 20 mints still existed. 19 repriced from $1.10 to $874.27. All stayed under $10,000. Labels did not change (`AVOID` stayed `AVOID`, VSOF stayed `SKIP`). Largest dollar move was JEANDIESEL, 991.65 to 783.84. VSOF still has no `pump_swap_pool`. A different DexScreener pair for VSOF was not used as a price.

### DexScreener, same baseline mints, 2026-09-23T12:10:24Z

Public `https://api.dexscreener.com/latest/dex/tokens/...`. Not added to the production scan. On a shared pool, 2× DexScreener quote-side SOL × the snapshot SOL price matched the vault figure to the cent on 18 of 19 mints. `liquidity.usd` was within about 1% of the vault figure on 7 of 19, and about 3× to 40× the vault figure on the other 12, still under $3,000. The USD headline diverges when DexScreener `priceUsd` disagrees with the pool’s own reserve ratio. Quote-side SOL and the vault read are the same story. The USD headline often is not.

### Holder check, 2026-09-23T12:25:43Z

19 of 19 checked mints from the 12:08Z selected set: the largest token account is the pool base vault (PumpSwap account offset 139). Quote vault (offset 171) matched 0. Neither matched 0. One selected row had no finite `top1_holder_bps` and was not checked. `top1_holder_bps` on this set is the pool’s own coin-account share of supply. It is not a developer wallet and not a bundle. This used the same mints the question came from. The account identity was the new observation. It is not an edge.

## Hypotheses still open

From `PHASE_C_HYPOTHESES.md`. None is contradicted. None is an edge. Do not implement a scorer.

1. Newest-page turnover. One gap supported it (08:38Z and 12:08Z shared no mint). A later scan, gates unchanged, must show whether that repeats. Falsify if a later selected set still contains a large share of the prior mints, or if ages sit on older pages while newer graduated coins were available.
2. Quote-side match and USD divergence. Supported on the baseline reprice (18 of 19 to the cent). The one miss was not named. A later cohort is required before treating the match as general. Falsify if 2× quote SOL misses the vault by more than a cent on a shared pool, or if `liquidity.usd` diverges while `priceUsd` agrees with the reserve ratio.
3. The $10,000 floor is a right-tail label on this board. Median far below it; two names cleared it at 12:08Z; the baseline cleared none. Do not propose a new floor. Falsify the shape if a later snapshot’s median sits near $10,000 or most finite prints clear the floor. A later snapshot with zero clears would not falsify the baseline; it would falsify “every snapshot has names above the floor.”
4. Top holder may be the pool account. Settled for the 12:08Z set: it is the base vault. Still untested on any other cohort. Do not treat holder share as a feature on a new cohort until the same identity check is repeated.
5. BONNIE and CHICKEN have no forward vault read. Falsify “no forward read” by repricing those two mints. A later vault read is still not an edge by itself. Record the move, and do not call persistence a strategy.

## Next allowed step

Phase D, held-out only. As of 15:10Z, about three hours have passed since the 12:08Z scan. That is the first clock at which the deferred checks are worth running. One pass, then stop and reassess. Do not start Phase E in the same pass.

1. Run `rocket memecoin radar --json` once. Save a redacted snapshot next to the other artifacts, with `retrieved_at`. Do not change code unless a bug blocks the measurement.
2. Selected-set overlap versus the 12:08Z mints in `PHASE_B_SCAN.json`. Report the count shared. This challenges hypothesis 1.
3. Distribution of finite `liquidity_usd` on the new selected set (n, min, p25, p50, p75, p90, max) and how many clear $10,000. This challenges hypothesis 3. Do not edit `LIQUIDITY_FLOOR_USD`.
4. Reprice BONNIE and CHICKEN with the same quote-vault method. Record liquidity then, liquidity now, and whether the frozen classifier would still say `WATCH_ENTER`. This challenges hypothesis 5. No fill, no order.
5. On the new cohort only, optional DexScreener quote-side check using the same comparison as Phase B. If the request fails, write that and continue. Do not add DexScreener to the production scan.
6. For any new row whose `top1_holder_bps` would be discussed, repeat the base-vault identity check before calling it a holder feature.
7. Write `artifacts/memecoin_radar/PHASE_D_HELDOUT.md`. State what was falsified, what survived as a description, and that surviving a description is not an edge. Compare with a dumb baseline: “the label does not persist” and “the mass of vault prints stays under $1,000.” Include timing. Slippage and failure stay unmeasured unless a public quote makes them observable without trading. Do not invent a fill.
8. Update `ROADMAP.md` only to point at that file.

If the held-out pass falsifies the open claims, stop. The conclusion remains `NO_EDGE_VALIDATED`. Do not write a strategy contract.

If something simple survives, say which claim and what would falsify it next. Still do not encode a shadow strategy in that same pass.

## Forbidden until a held-out result exists

- Phase E: shadow entries and exits, prospective paper trading, scheduling, bot integration, execution architecture.
- Changing the $10,000 floor, the 30-minute age floor, the state machine, or the ranker.
- A new scorer, a new workflow module, or a new mandatory provider.
- OS cron, launchd, GitHub Actions on a timer, Discord, copy-trading, slot-0 sniping, follower replay, JEV.
- Committing PR #27 data, printing `HELIUS_API_KEY`, or treating a `WATCH_ENTER` row as a buy.

## Reassess rule

After the held-out note, stop and say which phase is actually next. The evidence can demote the roadmap. A correlation on one cohort is not permission to build a bot.
