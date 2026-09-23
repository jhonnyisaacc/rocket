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

### C — Discover a few falsifiable hypotheses

Do not limit the search to current `WATCH_ENTER` gates. Do not implement a new scorer. A correlation is not an edge.

### D — Challenge only the strongest hypotheses

Use observations that were not used to invent them. Include timing, liquidity, slippage, and failure. Compare to simple baselines. Write a candidate strategy contract only if something survives.

### E — Shadow strategy before automation

Only if a candidate edge survives D: read-only hypothetical entries and exits, prospective results, `execution_enabled` false. Scheduling, bot integration, and execution architecture only after prospective evidence.

## Where this branch stops

Phase A is closed by the commit that puts this file, `PR30_AUDIT.md`, and the `HOW_TO_RUN.md` quarantine on `cursor/memecoin-radar-intake-f1ca`. Phase B is the lowest unfinished phase. It has not been started. Stop and reassess before any later phase begins.
