# Rocket research charter

Safety: `READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`. Execution is disabled.

The human-value contract is to determine whether a scientifically defensible BTC derivatives strategy can identify a small number of unusually attractive directional momentum opportunities, enter efficiently, manage systematically and express appropriately through futures/options — or terminate the line with preserved negative evidence. Desired behavior is sparse, deterministic, reproducible, cost-aware and bounded by an explicitly approved risk policy. An LLM has no discretionary trade override.

## Decisions reserved to the human

| Decision | Frozen value | Required before |
| --- | --- | --- |
| Rare/high-conviction opportunity: frequency, alert budget and conviction criterion | HUMAN_DECISION_REQUIRED | Strategy contract |
| Minimum economically meaningful effect and relevant benchmark | HUMAN_DECISION_REQUIRED | Economic strategy gate |
| Conservative venue fees, spread, slippage, funding, impact and cost stress | HUMAN_DECISION_REQUIRED | Executable strategy economics |
| Maximum acceptable drawdown and measurement horizon | HUMAN_DECISION_REQUIRED | Management/strategy contract |
| Maximum risk per trade and sizing convention | HUMAN_DECISION_REQUIRED | Management contract |
| Maximum leverage, margin and liquidation policy | HUMAN_DECISION_REQUIRED | Futures expression |
| Portfolio gross/net, correlated, directional and venue exposure limits | HUMAN_DECISION_REQUIRED | Portfolio/expression contract |
| Maximum pilot loss and stop/reset policy | HUMAN_DECISION_REQUIRED | Capital review |
| Capital authorization: venue, amount, instruments, duration, responsible human, revocation | HUMAN_DECISION_REQUIRED | Any real-capital pilot |
| Independent scientific reviewer identity/process | HUMAN_DECISION_REQUIRED | MOM-002 admission |

An existing proposal's numerical research thresholds (including #49's descriptive 40bp/80bp hurdles) are proposal evidence, not human economic or risk approval. Agents may neither invent these values nor fill them after seeing results. Human decisions must be dated, attributed, committed and reviewed before the affected contract is frozen. Changes require a recorded rationale before outcome access; prior tests remain consumed.

## STOP and terminal decisions

Failure is a successful research outcome. A required upstream FAIL kills dependent branches. There is no automatic successor or rescue experiment. Data infrastructure is built only for an admitted experiment or to fix an existing correctness bug. No full ALFRED history, macro warehouse, Cava/X backfill or options-surface history is presently admitted.

`STRATEGY_VALIDATED` requires a complete frozen strategy with forecast skill, reproducible setup, deterministic management, defensible derivative expression, conservative costs, explicit risk/leverage policy, historical robustness and prospective validation. It moves to `READY_FOR_CAPITAL_REVIEW`; agents stop. It grants no capital permission. Real capital needs an explicit human authorization of the pilot terms above in a separately reviewed process.

`RESEARCH_LINE_REJECTED` follows required gate failure when no independently admitted alternative remains. Preserve all negative evidence and stop. Missing evidence is BLOCKED with an explicit kill condition, never a permanent waiting room.

Routine admitted work needs no further prompting. Human intervention is normally limited to this charter, reviewer identity/process, acknowledgment of a future MOM-002 PASS before downstream decomposition, and the capital gate. Current program outcome: Active, with unresolved human decisions. [Decision issue #56](https://github.com/jhonnyisaacc/rocket/issues/56).
