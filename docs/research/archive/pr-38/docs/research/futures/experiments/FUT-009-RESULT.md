# FUT-009: delayed dollar-index BTC forecast, post-study 2024 result

Status: `GROSS_INCREMENTAL_AND_NET_FAILED_2024`, 2026-09-24. The
[source, rule and gates](FUT-009.md) were frozen in `38ff532`; the
[deterministic scorer](../../../../research/futures/fut009_score.py) was
committed in `7637a07` **before** reading any dollar-conditioned BTC
outcome. It scored only the first allowed year. The ignored local JSON
`fut009_2024_result.json` has SHA-256
`36fed603c9f570dcfc7427d88b8998e589246c66083d21fb066b11f137ee3d97`.
The scorer requires a passing 2024 report before it can load conditional
2025 BTC prices; no 2025 macro-conditioned outcome was scored.

| Frozen 2024-03-01–12-29 source window | Result | Gate |
| --- | ---: | --- |
| Scheduled UTC days / active positions | 304 / 209 | ≥150 active: **pass** |
| Long / short positions | 24 / 185 | Descriptive |
| Mean active BTC price gross | −8.229 bp | >0: **fail** |
| Same-active-date always-long gross | +8.177 bp | Control |
| Active incremental gross versus always-long | −16.406 bp | >0: **fail** |
| Mean scheduled-day price gross | −5.658 bp | Descriptive |
| Mean scheduled-day funding P&L | +1.426 bp | Actual settlements |
| Total target-change turnover | 132 notional-side units | Includes terminal flatten |
| Mean scheduled-day net, 5 bp/side | −6.403 bp | >0: **fail** |
| Mean scheduled-day net, 10 bp/side | −8.574 bp | >0: **fail** |

The 304 scheduled days include 95 cash days without a valid prior-date
Yahoo dollar-index observation. The source-active days all produced
positions after 541–749 resolved prior training pairs. The long subset's
mean gross was −0.230 bp and the short subset's was −9.267 bp; neither
is a selected rescue. March, April, June and July had positive scheduled
gross, as did December, while September and November were strongly negative. The longest
consecutive active run was five days. The 5 bp/side compounded return was
−23.40% and the 10 bp/side compounded return −28.30%; calendar-month
block bootstrap intervals for the daily net mean included zero at both
cost levels, so no multi-month precision claim follows.

The accounting reconciles independently from the report: −5.658 bp
scheduled price gross +1.426 bp funding −`5×132/304` bp cost = −6.403 bp
daily net. The same source-active-date always-long control yielded
+2.041 bp/day at 5 bp/side and +0.462 bp/day at 10 bp/side; the rolling
intercept-only control lost at both costs. The exact fitted dollar model
was mostly short in a period when the control's gross long return was
positive. This is a failed incremental forecast, not solely fee drag.

The Yahoo/ICE-labeled series is a sparse secondary proxy with documented
holiday gaps and no historical vintage guarantee. Its close is made
eligible only after the conservative frozen delay, and the BTC fill is
the next hourly open. Spread and impact beyond the side-cost assumption
remain unmodeled. Those limits prevent a paper-replication claim, but
cannot turn the observed negative gross and incremental gate into a pass
for this exact rule. The source paper's 2017–February 2024 spot VAR and
its fee table remain distinct.

**Decision:** close FUT-009 after the post-study 2024 cheap gate. Do not
switch to a 2024 month, long-only side, different dollar lag or source,
forecast threshold, fill clock, model or cost scenario. The conditional
2025 score and 2026 final holdout remain unread. No live decision or
production change follows.
