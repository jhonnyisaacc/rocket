# Memecoin Frontier

Status: current, 2026-09-24. One live question; update after each accepted or rejected experiment.

**Question:** Which features genuinely observable during the earliest token lifecycle contain information about later economically tradable outcomes after realistic execution?

## Current evidence and bottleneck

MC-001 established a reachable native Solana Pump log stream and measured a bounded prospective session: 2,458/2,458 signatures matched the independent index in fully observed interior slots; six CreateEvents and 437 TradeEvents decoded with the pinned official IDL; five create mints matched fetched transactions; 113/113 native non-Mayhem state transitions and 208/208 integer trade quotes reconciled. The first/last slots were excluded. This proves a viable read-only *research* acquisition path for that window. It does not establish a complete long-running panel, exact subsecond latency, inclusion/fill feasibility or tradable alpha. `main` still has no continuous strategy collector. See [MC-001](experiments/MC-001-RESULT.md).

## Next falsifiable step

MC-002 extended the covered stream to 180 seconds: 37,557/37,557 inner-slot signatures matched, 104 creates and 9,253 trades decoded, and 4,682/4,682 supported new-mint state transitions reconciled. The [frozen baseline result](experiments/MC-002-RESULT.md) left only 19 costed quotes from 104 launches, with three in its temporal evaluation slice. Twelve exits lacked sellable quote liquidity and ten entries lacked an as-of fee state. The small quoted subset and its positive two-name top-quartile evaluation mean cannot support an edge. The development top quartile was worse than all quoted names.

The next falsifiable question is whether the same simple rank survives when exit feasibility is treated as a **separate catastrophic-risk outcome**, then charged as a terminal-liquidity stress rather than omitted from the return subset. [MC-003](experiments/MC-003-FROZEN.md) keeps MC-002's clocks, size, score and costs on an independent longer cohort. No new threshold or learned model is justified yet. If those outcomes remain too sparse, improve prospectively measured fee/entry state and continue collecting covered cohorts; do not rescue a positive quote subset through retuning.

## Decision today

Status `OPEN`: early event acquisition is technically viable in the tested windows. Economic ranking and executable exits remain unproven. MC-003 is the next independent risk/economic falsifier. No model or signal is promoted.
