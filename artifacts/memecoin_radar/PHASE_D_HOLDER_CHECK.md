# Phase D — holder check

NO_EDGE_VALIDATED. Human-gated. Read-only.
A WATCH_ENTER row is not a buy. `execution_enabled` stays false. `edge` stays `NO_EDGE_VALIDATED`.

One hypothesis only, from `PHASE_C_HYPOTHESES.md`: `top1_holder_bps` may be the pool's own token account rather than a developer or a bundle. Floors, gates, ranking, the CLI, and the scorer were left as they are. No cron was added.

## What was not retested

Newest-page turnover, the frozen $10,000 tail, the DexScreener quote-side comparison, and a forward read of the 12:08Z BONNIE and CHICKEN `WATCH_ENTER` rows were left alone. A few minutes after 12:08Z is not a held-out window for those. Those Phase C claims are still unchallenged.

## Check

The rows are the selected set in `PHASE_B_SCAN.json` (`decision_time` 2026-09-23T12:08:10.046799+00:00). A row was eligible when `top1_holder_bps` was finite. The scan does not store a pool address. The pool was read from the public coin field `normalize_pump_coin` already uses, `pump_swap_pool`.

The live read was 2026-09-23T12:25:43.784444+00:00. Helius `getTokenLargestAccounts` supplied the largest token account. Helius `getAccountInfo` supplied the pool. The account had to be owned by the PumpSwap program and start with the Pool discriminator the radar already checks. The quote vault is the 32 bytes at offset 171. The same layout exposes the base vault as the 32 bytes at offset 139 (`pool_base_token_account`, the field before the quote vault). The base mint at offset 43 matched the coin mint on every checked pool, so that base vault was used. The scan did not store the 12:08Z account address, so this read names the largest account at 12:25Z.

| Count | n |
| --- | ---: |
| Selected rows | 20 |
| Finite `top1_holder_bps` | 19 |
| Of those, with a pool address | 19 |
| Mints checked | 19 |
| Largest account is the pool quote vault | 0 |
| Largest account is the pool base vault | 19 |
| Largest account is neither | 0 |

The one selected row with no finite `top1_holder_bps` was not checked. On 18 checked pools the quote mint at offset 75 was wrapped SOL. On 1 checked pool that mint was a different address. The two vaults were distinct on all 19. The largest account was the base vault on that pool as well.

No owner was named for a neither result. There was no neither result.

## Settled

On all 19 checked mints the largest token account is the pool base vault. It is the pool's own token account for the coin. The hypothesis is settled for this set. `top1_holder_bps` here is that vault's share of supply. It is not evidence of a developer wallet or a bundle.

This is not an edge. The mints are the selected set the hypothesis was read from. The account identity was absent from `PHASE_B_UNIVERSE.md` and from `PHASE_C_HYPOTHESES.md`. This file supplies that identity. It is not a new cohort, and it does not compare timing, liquidity, slippage, or failure to a baseline. No candidate strategy contract follows. `edge` stays `NO_EDGE_VALIDATED`. `execution_enabled` stays false. A WATCH_ENTER row is not a buy.
