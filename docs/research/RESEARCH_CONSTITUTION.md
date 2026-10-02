# Rocket research constitution

Authority: this page defines reusable research method. A strategy pillar applies it to one domain; a frontier names the one current question. Experiment and component ledgers record evidence. Historical PRs and notes remain evidence, never current instructions.

1. State a falsifiable question, mechanism, baseline, cheapest useful falsifier, data requirements, and decision rule before scoring outcomes. Freeze structural parameters and record the specification and source revision. Count materially different trials, including failures.
2. Use information available at each decision time. Preserve raw timestamps, publication or settlement times, missing values, delistings, and acquisition provenance. Do not project a current universe backward. Use completed bars and a specified subsequent fill; never substitute a different clock without a new specification.
3. Separate directional forecast, candidate ranking, context, entry timing, and portfolio risk. Measure a component against the same base strategy with an ablation. A reduced trade count is not proof of better signal.
4. Include fees, slippage, spread assumptions, funding, turnover, missing-data handling, and cost stress. Report signal-level outcomes and portfolio outcomes separately. Never call overlapping events independent observations.
5. Use a chronological discovery/OOS split at the cheap gate. Check asset, period, side, concentration, and broad parameter stability. Escalate promising candidates to walk-forward, uncertainty estimates, multiple-trial accounting, and an untouched holdout. Use purging or embargo when labels overlap; reserve prospective shadow for a frozen candidate.
6. Prefer simple, interpretable rules. A narrow optimum, post-result filter, or late switch of the primary metric weakens evidence. Record failure attribution (`NO_SIGNAL`, `NO_SAMPLE`, `COST_DRAG`, `DATA_LIMITATION`, `OVERFIT`, `REGIME_DEPENDENT`, `CONCENTRATION`, `SURVIVORSHIP_BIAS`, `FACTOR_BREAKDOWN`, or a documented other reason).
7. For each conclusion state what the evidence says, what it does not say, why, and what would reopen it. Reopen a rejection only for independent data, a demonstrated bug, a genuinely different mechanism, replication, or operator direction. A rule change receives a new experiment ID.

Component promotion: `UNTESTED` → `DISCOVERY_SIGNAL` → `OOS_CANDIDATE` → `ROBUST_COMPONENT`. Strategy promotion: `RESEARCH` → `CANDIDATE` → `FROZEN` → `SHADOW` → `ACCEPTED`. A backtest cannot skip to `ACCEPTED`. A frozen shadow records each decision and exact specification immutably; changed rules start a new version.

## Family direction admission

Experiment validity and permission to continue a research family are separate.
Each pillar must maintain a canonical family audit and written admission ledger.
Before a new contract or outcome score, record a distinct mechanism, motivation
independent of inspected favorable outcomes, causal observability, source
feasibility, product/execution fit, cheap falsifier, fresh chronology, explicit
family budget/stop rule and independent review. Denials remain in the ledger.
The proposer cannot approve its own admission or fabricate operator approval.
Each result suspends automatic continuation pending family review; data and
execution calibration do not erase negative economic evidence.

Futures applies this through [its family admission gate](futures/EXPERIMENT_ADMISSION.md).
Other pillars may enforce a stronger domain-specific machine-readable gate;
this written futures gate grants no exemption from those controls. The pending
memecoin PR #37's governance remains scoped to its pillar and implementation.
Shared policy must preserve both domains' admission requirements when reconciled.

The futures 2026 final holdout remains sealed for exploration. Access requires
an independently reviewed frozen promotion candidate, explicit authorization
under the pillar's promotion protocol and a recorded one-time evaluation plan.
A new paper, admitted cheap trial or source availability does not authorize it.
