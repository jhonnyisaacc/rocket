# Phase B — observable universe

NO_EDGE_VALIDATED. Human-gated. Read-only.
A WATCH_ENTER row is not a buy. `execution_enabled` is false. `edge` stays `NO_EDGE_VALIDATED`.

This file measures one new snapshot and re-reads the baseline 20. It does not change floors, the age window, gates, or ranking. Percentiles below describe this snapshot. They are not a proposed floor.

## Clocks

The forward gap is a few hours of clock time. It is not an edge.

| Clock | Time |
| --- | --- |
| Baseline `decision_time` | 2026-09-23T08:38:52.533836+00:00 |
| New scan `decision_time` | 2026-09-23T12:08:10.046799+00:00 |
| Baseline vault re-read | 2026-09-23T12:10:13.237002+00:00 |
| DexScreener `retrieved_at` | 2026-09-23T12:10:24.274547+00:00 |

From the baseline decision to the vault re-read is 3 hours 31 minutes (12681 seconds). Age on every baseline mint moved by that same 12681 seconds, because `event_time` was left at the baseline creation time.

## New scan

`rocket memecoin radar --json` once. Exit 0. Redacted copy: `PHASE_B_SCAN.json`. The key-bearing URL is not in that file.

- workflow `memecoin.radar`, research `INSUFFICIENT_EVIDENCE`, coverage `OBSERVED`
- `edge` `NO_EDGE_VALIDATED`, `execution_enabled` false
- notice: A WATCH_ENTER row is not a buy.
- selected 20. Counts: `WATCH_ENTER` 2, `SKIP` 2, `TOO_EARLY` 0, `AVOID` 16
- Helius `HEALTHY`: `getAccountInfo+getTokenLargestAccounts+quoteVault confirmed=20 liquidity=19`
- The two `WATCH_ENTER` rows are BONNIE (`liquidity_usd` 11252.17, age 3052, reason `floors_met_not_an_entry`) and CHICKEN (`liquidity_usd` 10356.06, age 3376, same reason). A WATCH_ENTER row is not a buy.
- The two `SKIP` rows are burrito (`helius_confirm_missing`, `liquidity_unknown`) and doge (`liquidity_unknown`).
- None of the 20 baseline mints are in this selected set. The scan is a new cohort, not a reprice of the baseline.

### Distributions on the new selected rows

Nulls are left out of `n`. Percentiles are linear interpolation between ranks (type 7): the position is `(n−1)×p`.

- `liquidity_usd`: n=18 (2 null), min 4.23, p25 63.15, p50 265.75, p75 826.88, p90 3969.08, max 11252.17
- `age_seconds`: n=20, min 2030, p25 2355.2, p50 3105.0, p75 3492.0, p90 3735.8, max 3771
- `top1_holder_bps`: n=19 (1 null), min 1983, p25 7890.0, p50 9650, p75 9977.0, p90 9986.2, max 9987

`p90` of liquidity sits where it does because two vault prints are above the frozen $10,000 floor and the other sixteen finite prints are at or below 1231.80. The median finite print is 265.75. That split is a description of this snapshot.

## Baseline 20, repriced

The new scan did not include these mints, so they were not taken from its selected rows. Each mint was read again with the same vault method the scan uses:

1. Public `GET https://frontend-api-v3.pump.fun/coins/{mint}` for `pump_swap_pool` (the field `normalize_pump_coin` already reads).
2. Helius quote-vault balance on that pool, then `2 × quote tokens × solUsd`, via the existing confirm path.

`solUsd` at the re-read was the pump.family sales field, 116.91410234863712. A missing pool or a zero vault stays null. No price was filled in.

All 20 mints were found again (`mint_exists` true). 19 have a new quote-vault price. VSOF (`H1vNzAivJt1rjeEFNfCmGcDwUEoLmYAcCAYYysnVpump`) still has no `pump_swap_pool` on the coin JSON, so its vault price was not reobserved. It stays null, and the frozen classifier still labels it `SKIP`.

`state now` is that same frozen classifier at the re-read clock. These 20 were not re-selected by the scan. Every previously `AVOID` row is still `AVOID` with `liquidity_below_floor`. None of them is `WATCH_ENTER`.

| Asset | Mint | Liquidity then | Liquidity now | Age then | Age now | State then | State now | DexScreener liquidity.usd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| $CATTY | `8yM4GdERwWY6tTAeYZCaLBTMNoNFDDNRDBNWMtc8pump` | 569.97 | 556.22 | 2154 | 14835 | AVOID | AVOID | 550.28 |
| My | `GdQ4RWKTRhxV3sjTWHq44hoEF7DXGq6cmRqUoJqpump` | 4.32 | 3.20 | 2284 | 14965 | AVOID | AVOID | 3.24 |
| JEANWIFHAT | `5HGgqq3jWwUXQNRq57U2tPgrxCuzBXb28TbTj97vpump` | 811.81 | 802.90 | 2315 | 14996 | AVOID | AVOID | 2838.11 |
| CATO | `EJB24d7joVzRmwqgzrURzhYLcECVpaLQ1yVunH87pump` | 398.72 | 349.24 | 2412 | 15093 | AVOID | AVOID | 2414.80 |
| Hermès | `4Qow3ZCXcZiwA9a92p9cT3QVCfbScNW1RWaY3XUqpump` | 137.31 | 87.35 | 2428 | 15109 | AVOID | AVOID | 2137.73 |
| LOTTO | `9BZP8V8c9jWEzg9XysgtrbgRqFV7uDpR79ovUHKApump` | 89.72 | 68.50 | 2480 | 15161 | AVOID | AVOID | 2119.73 |
| JEANDIESEL | `BftUerqdgzTq43DSWETuqKGiLGWXV8hytwunHZSVpump` | 991.65 | 783.84 | 2497 | 15178 | AVOID | AVOID | 2782.72 |
| VSOF | `H1vNzAivJt1rjeEFNfCmGcDwUEoLmYAcCAYYysnVpump` | — | — | 2509 | 15190 | SKIP | SKIP | not the page pool |
| $CAT | `FHTRjumBtyp5JhEaJdqwD3jt3YgZG9DvXL32ZSjzpump` | 190.98 | 174.66 | 2718 | 15399 | AVOID | AVOID | 174.35 |
| TRUMP | `F18vqhUREuw92g1pKwWrbxFzgcWBBrR42YPSMdPupump` | 73.24 | 72.41 | 2756 | 15437 | AVOID | AVOID | 2106.53 |
| ₽ | `gS7ZrM3qcMvqRyzv8J5oymLtA87PiZqUw6LY6z6pump` | 210.15 | 207.86 | 2819 | 15500 | AVOID | AVOID | 2280.51 |
| Robinhood | `CSV4zFDByo6hDCKQcGWXTo74tnuAP9eHYMDXmt9yeTMB` | 73.88 | 75.23 | 2861 | 15542 | AVOID | AVOID | 2114.96 |
| $CAT | `65hfQWtRTXYUW87bQ6xrckZQwar7GV43g5rBXLPHpump` | 384.31 | 378.53 | 2908 | 15589 | AVOID | AVOID | 378.86 |
| UNA | `3sipCaYtDyEDr6etQUV3figZYgHp6pyEHtgGRWXupump` | 9.85 | 8.80 | 2930 | 15611 | AVOID | AVOID | 8.88 |
| AHOOD | `4ZcUyaR9WTxJhtftxT6rocEhmSLyVDMvKTg7E65mpump` | 2.62 | 1.10 | 3162 | 15843 | AVOID | AVOID | 1.11 |
| BFC | `29edg1RAgo8o4cb5Y6AYdwJrq2d5kQgJSWMzgGQhpump` | 50.66 | 51.74 | 3452 | 16133 | AVOID | AVOID | 2079.92 |
| ToadPepe | `AHWDmozZb5ZVLs6VxkscGYWS5QN7TJqSTQSqnDxDpump` | 896.85 | 874.27 | 3458 | 16139 | AVOID | AVOID | 2941.28 |
| FAP | `3spFENA9i6yqrk44L6QorbvwzrYAQYf561LYEkiSpump` | 682.66 | 669.35 | 3461 | 16142 | AVOID | AVOID | 2669.90 |
| $CAT1 | `B2r35cd7np1bphGYR99DRKM93yLgMhAR8RwdyK8Ypump` | 61.62 | 50.96 | 3536 | 16217 | AVOID | AVOID | 51.59 |
| AHOOD | `6UbBD7hn9fhXZoAefpNWkRGAbiJfwisDT3Cf8LTwpump` | 468.55 | 463.44 | 3644 | 16325 | AVOID | AVOID | 2513.86 |

On the 19 priced vaults, liquidity now runs from 1.10 to 874.27. The largest dollar move is JEANDIESEL, 991.65 to 783.84. All 19 stayed under the frozen $10,000 floor. That is a few-hour reread of one cohort, not evidence of an edge.

## DexScreener

Public request, not added to the scan.

- URL: `https://api.dexscreener.com/latest/dex/tokens/8yM4GdERwWY6tTAeYZCaLBTMNoNFDDNRDBNWMtc8pump,GdQ4RWKTRhxV3sjTWHq44hoEF7DXGq6cmRqUoJqpump,5HGgqq3jWwUXQNRq57U2tPgrxCuzBXb28TbTj97vpump,EJB24d7joVzRmwqgzrURzhYLcECVpaLQ1yVunH87pump,4Qow3ZCXcZiwA9a92p9cT3QVCfbScNW1RWaY3XUqpump,9BZP8V8c9jWEzg9XysgtrbgRqFV7uDpR79ovUHKApump,BftUerqdgzTq43DSWETuqKGiLGWXV8hytwunHZSVpump,H1vNzAivJt1rjeEFNfCmGcDwUEoLmYAcCAYYysnVpump,FHTRjumBtyp5JhEaJdqwD3jt3YgZG9DvXL32ZSjzpump,F18vqhUREuw92g1pKwWrbxFzgcWBBrR42YPSMdPupump,gS7ZrM3qcMvqRyzv8J5oymLtA87PiZqUw6LY6z6pump,CSV4zFDByo6hDCKQcGWXTo74tnuAP9eHYMDXmt9yeTMB,65hfQWtRTXYUW87bQ6xrckZQwar7GV43g5rBXLPHpump,3sipCaYtDyEDr6etQUV3figZYgHp6pyEHtgGRWXupump,4ZcUyaR9WTxJhtftxT6rocEhmSLyVDMvKTg7E65mpump,29edg1RAgo8o4cb5Y6AYdwJrq2d5kQgJSWMzgGQhpump,AHWDmozZb5ZVLs6VxkscGYWS5QN7TJqSTQSqnDxDpump,3spFENA9i6yqrk44L6QorbvwzrYAQYf561LYEkiSpump,B2r35cd7np1bphGYR99DRKM93yLgMhAR8RwdyK8Ypump,6UbBD7hn9fhXZoAefpNWkRGAbiJfwisDT3Cf8LTwpump`
- `retrieved_at` 2026-09-23T12:10:24.274547+00:00
- HTTP 200, 30 pair objects. Not mint-less.

For 19 mints the pumpswap `pairAddress` is the page's `pump_swap_pool`. On 7 of those, `liquidity.usd` is within about 1% of the vault figure ($CATTY, My, both $CAT rows, UNA, the 1.10 AHOOD, $CAT1). On the other 12, `liquidity.usd` is about 3× to 40× the vault figure, still under $3,000 on this response.

A second GET of the same URL in this session showed why. DexScreener `liquidity.usd` tracks token reserves × `priceUsd` plus quote reserves × the SOL price. The vault figure is 2 × quote reserves × the SOL price. On 18 of the 19 same-pair mints, 2 × DexScreener's quote SOL × the reprice SOL price matched the vault figure to the cent. The USD headlines diverge when `priceUsd` is far from the pool's own reserve ratio. The quote-side SOL and the vault read tell the same story. The `liquidity.usd` headline often does not.

VSOF is not that comparison. The page pool is null, so the vault method has no price. DexScreener returned a different pumpswap pair (`7q6uSK2Ge96GgEBF8c7CbXXHKcWhwjciQPXWcbonSeMz`) whose base token is the VSOF mint, with `liquidity.usd` 1410705.17. That number is not a vault price and is not used as one.

## What this dataset teaches

- The baseline feed was a cohort. A few hours later the selected 20 are different mints. Intake is the newest pages, so the labeled set turns over even when nothing about the gates changes.
- Those 19 repriced vaults stayed under $1,000. Their frozen labels did not change. The clock advanced; the dollar prints moved by cents up to about $208.
- The new snapshot's vault prints are mostly still small (median finite `liquidity_usd` 265.75) and include two above the frozen $10,000 floor. Both facts are this snapshot. The two labels are `floors_met_not_an_entry`.
- On a shared pool, 2× quote-vault matches DexScreener's quote-side SOL. DexScreener's USD headline is a different arithmetic and often a different number.

## What it cannot yet teach

- Any edge. `edge` stays `NO_EDGE_VALIDATED`. A few hours on 20 mints is not a test that a label survives.
- Whether BONNIE or CHICKEN would still clear the frozen floor later, or what a fill, a fee, or slippage would have been. They were not repriced here. A WATCH_ENTER row is not a buy.
- Whether the baseline cohort's small dollar moves are typical of other cohorts.
- A vault price for VSOF. The page still has no pool. The large DexScreener pair was not adopted.
- Developer identity. `dev_hold` is still `UNKNOWN`. `top1_holder_bps` on the new scan is only a largest-account share.

## Questions worth testing later

These are questions. They are not new floors and not a scorer.

- For a mint the frozen gates label `WATCH_ENTER`, what does the same quote-vault read show a few hours later?
- When DexScreener `priceUsd` and the pool reserve ratio disagree, which number moves, and does the gap close?
- How often does a later selected set still show a right tail above the frozen floor, and how often is the mass under $1,000?
- For a mint whose page JSON has no pool, is the vault method blind to a pool that other public pages name, as with VSOF here?

Phase C has not been started.
