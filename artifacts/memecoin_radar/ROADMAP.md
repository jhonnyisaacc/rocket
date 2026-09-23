# Memecoin radar roadmap

NO_EDGE_VALIDATED. Human-gated. Read-only.
A WATCH_ENTER row is not a buy. `execution_enabled` stays false. `edge` stays `NO_EDGE_VALIDATED`.

This is research infrastructure. It is not a strategy.

## Rule

Only the lowest unfinished phase may be worked.

After Phase A, stop and reassess. If later evidence shows the direction is wrong, the next phase may be changed before more work starts. `NO_EDGE_VALIDATED` is an acceptable conclusion.

## Phases

### A — Audit and freeze the baseline

Done when this file, `PR30_AUDIT.md`, and the `HOW_TO_RUN.md` quarantine are on the branch.

The quarantine is the `LATER_NOT_NOW` section: the cron notes, the `*/5` crontab, and the sentences that tell a bot to run `radar` on a schedule.

### B — Understand the observable universe

Distributions, measurement trust, and forward outcomes from point-in-time rows. Extra sources such as DexScreener only for validation or missing context, not mandatory. Do not optimize thresholds. End with what the data teaches, what it cannot teach, and which questions are worth testing.

The measurement for this branch is `PHASE_B_UNIVERSE.md`, with the scan in `PHASE_B_SCAN.json`. Floors were not changed.

### C — Discover a few falsifiable hypotheses

The hypotheses for this branch are `PHASE_C_HYPOTHESES.md`, read off `PHASE_B_UNIVERSE.md`. Do not limit the search to current `WATCH_ENTER` gates. Do not implement a new scorer. A correlation is not an edge. None of these hypotheses is an edge. The holder-account claim has one check in `PHASE_D_HOLDER_CHECK.md`. The other Phase C claims are still unchallenged.

### D — Challenge only the strongest hypotheses

Use observations that were not used to invent them. Include timing, liquidity, slippage, and failure. Compare to simple baselines. Write a candidate strategy contract only if something survives.

The one check on this branch is `PHASE_D_HOLDER_CHECK.md`. It tests only whether `top1_holder_bps` is the pool's own token account. The other claims in `PHASE_C_HYPOTHESES.md` are still unchallenged. Nothing here is an edge. No candidate strategy contract. `edge` stays `NO_EDGE_VALIDATED`. `execution_enabled` stays false. A WATCH_ENTER row is not a buy.

### E — Shadow strategy before automation

Only if a candidate edge survives D: read-only hypothetical entries and exits, prospective results, `execution_enabled` false. Scheduling, bot integration, and execution architecture only after prospective evidence.

## Where this branch stops

Phase A is closed by the commit that puts this file, `PR30_AUDIT.md`, and the `HOW_TO_RUN.md` quarantine on `cursor/memecoin-radar-intake-f1ca`. Phase B's measurement is `PHASE_B_UNIVERSE.md`. Phase C's hypotheses are `PHASE_C_HYPOTHESES.md`. Phase D's holder check is `PHASE_D_HOLDER_CHECK.md`. The other Phase C claims are still unchallenged. `edge` stays `NO_EDGE_VALIDATED`. `execution_enabled` stays false. Stop and reassess before any later phase begins.
