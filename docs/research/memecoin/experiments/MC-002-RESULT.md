# MC-002 result — five-second curve progress

Status: `OPEN` / no strategy promotion, 2026-09-24. The predeclared [design](MC-002-FROZEN.md) was applied once to an independent 180-second prospective stream. This is a costed **static-state quote proxy**, not observed fills.

## Data and protocol gate

The read-only session received 37,694 Pump log notifications and 104 successful create hints. In fully observed interior slots 450058957–450059625, **37,557/37,557 signatures** matched 39 independently queried program-index pages. The first and last observed slots are excluded. The median whole-second block-timestamp to websocket receipt gap was 1.323 seconds (p90 1.749); this is an imprecise event-age measure. Pinned IDL decoding yielded 104 CreateEvents and 9,253 TradeEvents with zero layout errors. The five-second point-in-time rows use raw frame receipt clocks, not block time as availability.

For created native-SOL, non-Mayhem mints, **4,682/4,682** adjacent trade-state transitions reconciled; 1,121 Mayhem/other-quote transitions were not tested with that formula. Across the whole capture, 6,887 supported native non-Mayhem trade quotes reproduced observed amounts/fees with no material mismatch. Six exact-input events had an unexplained **one-lamport** protocol-fee excess relative to the simple ceiling formula; the audit records this tolerance explicitly. One zero-cash dust sell is excluded from the economic quote model. The creator fee was zero for trades whose event creator was the default address, despite a 30 bps configured field; the model now honors that event fact. These findings are scoped to the pinned protocol revision and observed cohort.

Evidence: [`mc002-capture-20260924.tar.gz`](../data/mc002-capture-20260924.tar.gz), SHA-256 `7d2e3c8cd768f925aa9688e4e7e3464043fe44f712d36d9060f45aa68e73ba94`. It contains the raw segment, all 39 index pages, manifest, decoded observations, PIT snapshots, full universe and both result versions. Extract to a new directory, then run `python scripts/research/memecoin_audit.py DIRECTORY --offline --max-pages 60` and `python scripts/research/memecoin_baseline.py DIRECTORY`. That offline replay reproduced coverage and result counts.

## Frozen baseline result

| Population | Count |
| --- | ---: |
| All create events | 104 |
| Excluded by predeclared domain/coverage gate | 63: 37 without a full 67-second window; 12 Mayhem; 14 non-native quote |
| Eligible for a five-second score | 41 |
| Outcome censored | 22: 10 without an as-of entry fee state; 12 without sellable exit liquidity |
| Costed quotes available | 19 |

The 70/30 chronological split assigned 29 scored launches to development and 12 to evaluation. Development had 16 quoted returns: all-quoted mean **−14.36%**, while the predeclared top curve-progress quartile had eight quoted returns with mean **−27.84%**. Evaluation had only **three** quoted returns; its all-quoted mean was **+0.16%**, and its top quartile had two quoted returns with mean **+4.66%**. The top score had ties, and nine of twelve evaluation launches lacked a numeric exit outcome. These numbers cannot establish a repeatable ranking or economic edge. The tiny apparent positive evaluation difference is especially sensitive to one name and informative censoring.

An initial script version incorrectly labeled the twelve unavailable exits `NO_FILL`. The frozen design required censoring; the corrected result uses `CENSORED`, and the original result is preserved in the archive as `mc002-result-pre-censor-fix.json`. Quoted-return values did not change. This was a bookkeeping correction, not parameter tuning.

## Allowed and forbidden conclusions

Allowed: bounded early-launch acquisition, point-in-time event features and native non-Mayhem curve arithmetic work for the verified window. Under the frozen simple policy, many candidates cannot be assigned a valid 60-second quote outcome, and development's top curve-progress names were worse than its quoted universe.

Forbidden: a validated `ENTER` rule, a profitable curve-progress factor, a clean negative proof about all early memecoin features, or actual fill/execution reliability. The quote proxy resets historical market states after hypothetical fills and assumes 2-second latency, 2% adverse slippage each leg and a historical 155,000-lamport network cost each leg. No transaction was submitted.

Next implication: model failed exit feasibility as a separate catastrophic-risk outcome, obtain an independent longer cohort with the same frozen clocks/score, and stress the missing-entry and exit-failure cases before more model complexity. See the current Frontier.
