# Memecoin Frontier

Status: current, 2026-09-24. One live question; update after each accepted or rejected experiment.

**Question:** Which features genuinely observable during the earliest token lifecycle contain information about later economically tradable outcomes after realistic execution?

## Current evidence and bottleneck

MC-001 established a reachable native Solana Pump log stream and measured a bounded prospective session: 2,458/2,458 signatures matched the independent index in fully observed interior slots; six CreateEvents and 437 TradeEvents decoded with the pinned official IDL; five create mints matched fetched transactions; 113/113 native non-Mayhem state transitions and 208/208 integer trade quotes reconciled. The first/last slots were excluded. This proves a viable read-only *research* acquisition path for that window. It does not establish a complete long-running panel, exact subsecond latency, inclusion/fill feasibility or tradable alpha. `main` still has no continuous strategy collector. See [MC-001](experiments/MC-001-RESULT.md).

## Current falsifier and next step

MC-002 extended the covered stream to 180 seconds: 37,557/37,557 inner-slot signatures matched, 104 creates and 9,253 trades decoded, and 4,682/4,682 supported new-mint state transitions reconciled. The [frozen baseline result](experiments/MC-002-RESULT.md) left only 19 costed quotes from 104 launches, with three in its temporal evaluation slice. Twelve exits lacked sellable quote liquidity and ten entries lacked an as-of fee state. The small quoted subset and its positive two-name top-quartile evaluation mean cannot support an edge. The development top quartile was worse than all quoted names.

[MC-003](experiments/MC-003-RESULT.md) applied the same frozen rank and costs to a new 300-second cohort. An independent second-provider index matched 38,941/38,941 interior signatures; 102 creates and 12,901 trades decoded. Of 52 eligible launches, 40 had quoted exits and 12 lacked sellable exit liquidity. The held-out quoted mean was **−8.99%** across 11 names; the top curve-progress quartile was **−8.05%** across three. With the frozen zero-recovery exit stress, held-out means were **−33.67%** across all 15 scored names and **−31.42%** across the top four. Development's top quartile was worse than the full group. These results reject the unchanged five-second curve-progress rank as an entry basis under this cost scenario. The stress is a scenario, not observed liquidation.

The next falsifiable question is whether genuinely early survival and manipulation-risk observations, coupled with transaction-level inclusion and exit feasibility, can improve net outcomes on new covered time windows. Acquire longer prospective panels and verify transaction balance deltas, observed entry failure, fees and exit routes before specifying that test. Preserve all unknown and unavailable outcomes. Do not retune the failed curve-progress cutoff on MC-002/MC-003.

[MC-004](experiments/MC-004-RESULT.md) calibrated one part of that gate against 56 hash-selected MC-003 transaction records: all were retrieved and matched stream identity/slot. The median whole-transaction fee was 117,500 lamports for sampled single buys and 100,000 for sampled single sells, with 15/48 above the earlier 155,000-lamport per-leg scenario and large outliers. Token-account deltas were consistent with event amounts in 47/48 single-event transactions; the remaining buy created its mint in the same transaction and lacked a pre-balance. This does not measure a hypothetical Rocket order's inclusion or exit route. The next fresh panel must collect those facts and test prespecified survival/risk features, rather than further score tuning on MC-002/MC-003.

## Decision today

Status `OPEN`: early event acquisition is technically viable in the tested windows. The simple curve-progress entry rank is rejected under the frozen proxy; broader economic ranking and executable exits remain unproven. No model or signal is promoted.
