# Phase C — falsifiable hypotheses

NO_EDGE_VALIDATED. Human-gated. Read-only.
A WATCH_ENTER row is not a buy. `execution_enabled` stays false. `edge` stays `NO_EDGE_VALIDATED`.

These claims are read off `PHASE_B_UNIVERSE.md` only. Floors, the age window, gates, ranking, and the classifier stay as they are. None of these is an edge. Phase D has not started.

A correlation worth checking is a relationship already visible in that measurement, which a later snapshot could confirm or knock down. Evidence of an edge would be a result on observations that were not used to write the claim, where a label still beats a simple baseline after timing, liquidity, slippage, and failure. This file has the first kind only.

## Status

None of the five is contradicted by `PHASE_B_UNIVERSE.md`.

| Hypothesis | Contradicted | In this file | Still untested |
| --- | --- | --- | --- |
| Newest-page turnover | No | One gap: the 12:08Z selected set shares no mint with the baseline 20 | Whether turnover repeats |
| Quote-side match and USD divergence | No | Baseline reprice: 18 of 19 same-pair mints match to the cent | The unnamed miss, and any later cohort |
| Frozen floor as a right tail | No | Median far under $10,000 on both clocks; two clears at 12:08Z; zero on the baseline | Whether a later selected set still has that right tail |
| top1 may be the pool account | No | A largest-account share only. No account identity | The whole identity check |
| 12:08Z WATCH_ENTER has no forward read | No | BONNIE and CHICKEN were not repriced | Any later vault, fill, fee, or slippage |

## Newest-page turnover

**Claim.** The selected set is the newest pages, so the labeled set turns over within a few hours even when the gates do not change.

**This measurement.** Baseline `decision_time` is 2026-09-23T08:38:52.533836+00:00. The new scan `decision_time` is 2026-09-23T12:08:10.046799+00:00. None of the 20 baseline mints are in the new selected set. Ages on the new selected rows run from 2030 to 3771 seconds. Ages on the baseline rows ran from 2154 to 3644 seconds at the first clock, and from 14835 to 16325 seconds at the re-read. The file did not change the gates. State on the baseline rows stayed put: every `AVOID` is still `AVOID` with `liquidity_below_floor`, and VSOF is still `SKIP`. The turnover in this gap is membership of the selected set.

**Would falsify it.** A later scan, gates unchanged, a few hours after a prior scan, whose selected set still contains a large share of the prior mints. Or a selected set whose ages sit on older pages while newer graduated coins were available.

**Test.** This file holds one supporting gap, so the claim is not contradicted. Whether the labeled set turns over again is untested. A later held-out snapshot is required.

## Quote-side match and USD divergence

**Claim.** On a shared pool, 2 × the quote vault matches DexScreener's quote-side SOL, while DexScreener `liquidity.usd` diverges when `priceUsd` disagrees with the pool reserve ratio.

**This measurement.** For 19 baseline mints the pumpswap `pairAddress` is the page `pump_swap_pool`. On 18 of those 19, 2 × DexScreener quote SOL × the reprice SOL price matched the vault figure to the cent. On 7 of those 19, `liquidity.usd` is within about 1% of the vault figure. On the other 12, `liquidity.usd` is about 3× to 40× the vault figure, and still under $3,000 on that response. The file states that the USD headline diverges when `priceUsd` is far from the pool's own reserve ratio. VSOF is outside this claim: the page pool is null, and DexScreener returned a different pair.

**Would falsify it.** On a shared pool, 2 × DexScreener quote SOL × the same SOL price misses the vault figure by more than a cent. Or `liquidity.usd` sits far from the vault figure while `priceUsd` agrees with the pool reserve ratio. Or the USD figures agree while `priceUsd` is far from that ratio.

**Test.** This file can test the baseline reprice. That reprice does not contradict the claim: 18 of 19 match to the cent, and the USD split is the one the file describes. The file does not name the one same-pair mint that missed the cent, so the cause of that miss is untested. A later held-out snapshot is required before the match is treated as a property of a later cohort. Two reads of the same quote reserves are a correlation worth checking. They are not an edge.

## Frozen floor as a right tail

**Claim.** On this board the frozen $10,000 floor is a right-tail label: the median vault print sits far below it, and a few names can clear it.

**This measurement.** Finite `liquidity_usd` on the new selected rows: n=18, min 4.23, p50 265.75, p75 826.88, p90 3969.08, max 11252.17. Two prints are above the floor, BONNIE at 11252.17 and CHICKEN at 10356.06. The other sixteen finite prints are at or below 1231.80. Baseline vaults ran about 2.62 to 991.65. On the re-read the 19 priced vaults ran from 1.10 to 874.27, and all 19 stayed under the floor. The floor stays $10,000. This is a description of these snapshots. It proposes no new floor.

**Would falsify it.** A selected snapshot, same floor, whose median finite vault print sits near $10,000, or whose finite prints mostly clear the floor. BONNIE and CHICKEN already show that a name on this board can clear the floor. A later snapshot with no clears would leave that intact. It would falsify a reading that every snapshot has names above the floor. The baseline snapshot is that case inside this file: zero clears, and the mass under $1,000.

**Test.** The right-tail shape of the 12:08Z selected set is in the file and is not contradicted. How often a later selected set still shows a few names above the frozen floor, with the mass far below it, is untested. A later held-out snapshot is required for that rate.

## top1 may be the pool account

**Claim.** `top1_holder_bps` may be the pool's own token account rather than a developer or a bundle. That has to be checked before holder share is treated as a feature.

**This measurement.** On the new scan, `top1_holder_bps` is n=19 (1 null), min 1983, p25 7890.0, p50 9650, p75 9977.0, p90 9986.2, max 9987. `dev_hold` is `UNKNOWN`. The field is a largest-account share. The file does not name the account. A high share is compatible with a pool vault and compatible with a bundle. The file does not identify which one it is. This claim is not asserted.

**Would falsify it.** A check that the largest account is some other owner than the pool's token account. A check that the largest account is that pool account would settle the same question the other way. Either check is the test. Until one of them exists, holder share is not a feature.

**Test.** `PHASE_B_UNIVERSE.md` has no account identity, so it cannot test this claim. The hypothesis is untested. A later held-out check is required.

## 12:08Z WATCH_ENTER has no forward read

**Claim.** The `WATCH_ENTER` labels on BONNIE and CHICKEN at the 12:08Z scan have no forward read.

**This measurement.** BONNIE has `liquidity_usd` 11252.17, age 3052 seconds, reason `floors_met_not_an_entry`. CHICKEN has `liquidity_usd` 10356.06, age 3376 seconds, and the same reason. They were not repriced. No later vault, fill, fee, or slippage is attached to that clock. The baseline cohort had no `WATCH_ENTER` row. A WATCH_ENTER row is not a buy.

**Would falsify it.** A quote-vault re-read of those two mints, or a fill, fee, or slippage attached to that decision clock, inside this measurement. None of those is in the file.

**Test.** The file records the absence, so "no forward read yet" is the measurement, and it is not contradicted. Whether either mint would still clear the frozen floor later is untested. A later held-out snapshot is required. That later read would still not be an edge by itself.

## Correlation and edge

Worth checking on a later snapshot:

- Selected-set overlap a few hours apart, with the gates left fixed.
- Quote-side cents against the vault, and the USD gap against `priceUsd` versus the reserve ratio.
- Where the frozen floor sits in a later vault distribution.
- Whether the largest token account is the pool.
- A later quote-vault read of a mint the frozen gates labeled `WATCH_ENTER`.

None of these is an edge. `edge` stays `NO_EDGE_VALIDATED`. `execution_enabled` stays false. A WATCH_ENTER row is not a buy. Phase D has not started.
