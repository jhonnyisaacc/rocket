# MOM-002: continuous BTC breakout information test

**Status: `PENDING_INDEPENDENT_REVIEW`. No scorer is implemented or executed
by this proposal.** Contract version: `mom002-continuous-v1`; proposed freeze
date: 2026-10-02. The commit containing this file is the reviewable contract
identity. Approval must identify that commit and the approving reviewer.

**Terminal commitment: if MOM-002 fails its frozen out-of-sample predictive,
incremental or economic gates, this candidate-based BTC momentum research
line is closed.** There is no MOM-003 rescue, COT, macro, Cava, X/news, Pana,
ETH/SOL, replacement generator, changed horizon, more complex model or new
feature transformation. Failure does not prove all momentum anticipation
impossible; it means this line stops for lack of useful evidence. Insufficient
source or sample readiness means `BLOCKED_READINESS`, with no permission to
weaken gates or score a replacement. It authorizes collection/audit only.

## Authority and contamination

MOM-000 remains `STOP_INSUFFICIENT_FEASIBILITY`; MOM-001 remains
`NOT_ADMITTED_SAMPLE_GATE_FAILED`. Neither its binary target nor its gates
are amended. MOM-002 is separately authorized by the user's reconciliation
request and tests information in a continuous outcome, rather than admitting
the rejected rare-positive classifier. The preregistered MOM-000 source
vintage and exclusions remain fixed, including any anomalous close-time row
whose future handling is proposed separately by the source audit.

The 2019–2025 population, binary outcomes, excursions and end returns have
already been inspected in the descriptive census and previous Rocket work.
These years are development data, not a pristine holdout. No MOM-002 feature/
target association, fitted prediction, model comparison or gate result has
been inspected or computed for this proposal. Independent review must occur
before any of those operations. A later historical pass could admit only
prospective confirmation, never deployment or a claim of statistical
validation from an active collector alone.

## Hypothesis and fixed population

The hypothesis is that the inherited six fast market features contain
out-of-sample information about the direction-aligned magnitude of the next
seven days' BTC movement, beyond inherited price features and simple causal
benchmarks. The co-primary claims are positive forecast/outcome correlation
and an improvement in squared prediction error over Tier A. Useful economic
selection must also pass the separate, conservative gate below.

The population is the exact MOM-000 BTCUSDT spot crossing population from
2019-01-01 through 2025-12-31: **354 crossings**, including 219 UP and 135
DOWN; **107 globally 14-day-spaced crossings**, including 64 UP and 43 DOWN.
Those identities are frozen independently of model scores and outcomes.
Retain every identity in the report, including unscorable or UNKNOWN rows.
The candidate generator, inactive-to-active crossing rule, complete 30-day
history, UTC 00/04/08/12/16/20 cutoffs, decision at cutoff+5m, 4h aggregates,
42 preceding bars and 0.5-sigma breakout offset are inherited unchanged.
No filtering on binary success, eventual MFE or ex-post leg membership is
allowed. No 14-day primary target, altered barrier or additional asset enters.

For candidate e, freeze direction d in {-1,+1}, reference P0 (the final
completed 4h close at cutoff t), and S = sigma_t * sqrt(42), where sigma_t is
sample SD of the last 180 contiguous 4h log-close returns, including the
newly completed decision bar. The continuous outcome is exactly:

`y_e = d_e * log(P_close[t + 7 days] / P0_e) / S_e`.

The terminal close is the 1h close whose bar ends exactly at t+7d. As in
MOM-000, exclude the partly observable first hour: require the complete 167
hourly bars starting at t+1h and ending at t+7d. Availability is no earlier
than t+7d+5m; actual prospective receipt must also be eligible. Missing bars,
missing terminal close or nonfinite/nonpositive reference/scale make y
UNKNOWN. The continuous target does not stop at a binary barrier. A fully
observed both-barrier hour can make the binary label UNKNOWN while leaving
this end-return target observed; keep that distinction explicit. No target
winsorization, clipping, rank transformation or alternative horizon is allowed.

## Frozen feature packet and data admission

The packet inherits MOM-001, with the documented, unscored
`price-market-v2` relative-volume correction. Six values are fixed at each
original decision; no interaction, lag search, expansion or transformation
search is permitted.

| Feature | Exact transformation |
| --- | --- |
| `signed_return_24h` | d * log(spot close_t / spot close_t-24h) / (sigma_t * sqrt(6)) |
| `rv_ratio` | sample SD of last six 4h log-close returns / sample SD of last 180 |
| `relative_volume` | mean base volume of last six complete spot 4h bars / mean base volume of the immediately preceding 174 bars |
| `funding_24h` | d * sum of realized BTCUSDT perpetual funding rates for the three nominal settlement slots in (t-24h,t], with actual event clocks and publication eligibility as specified below |
| `oi_change_24h` | log(BTCUSDT perpetual total OI_t / total OI_t-24h), without multiplying by direction |
| `spot_perp_volume_ratio` | sum of spot quote volume / sum of perpetual quote volume over the same 24 complete hourly intervals ending at t |

The [Tier B source audit](TIER_B_SOURCE_AUDIT.md) establishes archive cadence
and timestamp semantics, but does not establish historical publication
receipts. Freeze these **reconstructed availability defaults**, before any
feature/target association inspection; they require independent reviewer
acceptance and do not certify authentic historical PIT:

| Source | Event clock retained | Assumed historical available_at |
| --- | --- | --- |
| Perpetual 1h kline | normalized bar end, in milliseconds | bar end +5m |
| Funding | actual millisecond `calc_time`, including subsecond offsets | max(actual `calc_time`, nominal settlement slot +5m) |
| OI metric | exact UTC `create_time`, in milliseconds | `create_time` +5m |

Every raw byte/checksum identity, current corrected vintage and actual
October 2026 acquisition receipt is retained. Ingestion is never backdated.
Historical reconstruction uses the explicit assumed availability; prospective
joins additionally require actual ingestion <= original decision. No archive
file delivery/LastModified timestamp is presented as original publication.

Funding kernel: require `funding_interval_hours == 8`. Identify the nominal
UTC settlement slot at 00/08/16 by flooring actual `calc_time` to an 8h
boundary; require offset in [0,1000) milliseconds. This fixed subsecond
validation covers all audited offsets of 0–47ms, rather than demanding a
false exact grid. Nominal membership, not an altered event timestamp, defines
the three slots in (t-24h,t]. Require exactly one unique finite realized rate
per expected slot, actual `calc_time` <= decision, and assumed available_at
<= decision. Missing slots, conflicting duplicates, other cadence or larger
offsets make funding UNKNOWN. Exact duplicate observations collapse. Current
slot funding at t+47ms remains a real event after cutoff but before the
t+5m decision; its assumed publication time is t+5m. Neither event time nor
ingestion is rounded backward. This is the same trailing-24h realized sum,
with an explicit nominal-settlement convention, not next-settlement funding.

OI kernel: use positive finite, contract-denominated `sum_open_interest`,
with no notional-USD fallback. The frozen sampling interval is five minutes;
`create_time` must lie on that UTC grid. For endpoints t and t-24h choose
the latest observation whose event <= endpoint and assumed available_at
<= the original decision. Require endpoint age <=5m, equal ages, and event
clocks exactly 24h apart. Never floor intraday snapshots to the daily archive
filename; never interpolate or substitute notional exposure. Collapse exact
duplicates only when the source/instrument/event/vintage identity and entire
parsed payload are equal; conflicting payloads at that identity make the
affected endpoint UNKNOWN, without choosing the more convenient value.
Report both observation clocks and ages. Complete within-file coverage and
conflict checks remain required across every admitted metrics day; three
verified sample files alone do not establish history-wide readiness.

Quote-volume kernel: require all 24 aligned complete spot and perpetual 1h
bars in [t-24h,t), finite nonnegative quote volumes, positive perpetual sum,
and both source availability clocks <= decision. Preserve spot's documented
timestamp-unit switch separately from futures milliseconds. Validate source
bar clocks/OHLC and apply the inherited frozen quarantine policy; no endpoint
fills or partial-window ratios are allowed. Any default the independent
reviewer rejects requires an explicitly versioned pre-score amendment and
renewed review, not a free parameter at fitting time.

Tier B readiness is pending the separate source audit. Missingness is never
imputed, given a predictive indicator or used to select winning events. A+B,
Tier A and the simple benchmarks are evaluated on the identical six-feature-
complete target-observed subset. A-only results on a broader population may
not substitute for the proposed incremental claim. Preserve missing counts
by feature, direction, year and reason. An independent reviewer may reject a
feature before scoring; that requires a new, explicitly recorded proposal
version and renewed review, never a silent post-result change.

## Model and causal benchmarks

Freeze one ridge linear model with separate unpenalized UP/DOWN intercepts
and common slopes. Direction is known at candidate time; two intercepts allow
different base drift without creating separate six-slope models. For training
rows, form 7d interval components using only mature admitted training events.
Give each row weight 1 / number of admitted training rows in its component,
then normalize weights to sum one. Compute weighted feature means and
population SDs in that training set only. A zero-variance feature becomes
zero after centering with slope fixed at zero; report it. Do not silently
drop a nonconstant feature. Standardize features, not the target.

The exact objective is:

`sum_e w_e * (y_e - a_direction(e) - beta dot z_e)^2 + sum_j beta_j^2`.

Thus ridge alpha is **1 on a mean-loss objective**, not 1 on an unspecified
sum-loss objective. Intercepts are unpenalized. No alpha search, model-family
search, target rescaling or nonlinear feature interaction is permitted.
Fit the unique ridge optimum with a deterministic solver; persist package/
solver versions, normalization constants, coefficients and training identities.

Benchmarks on exactly the same rows, training weights and folds:

1. B0: the training weighted mean y for the candidate direction.
2. B1: ridge with `rv_ratio` only and the same two intercepts and alpha.
3. Tier A: ridge with the first three features and the same intercepts/alpha.
4. Unfiltered candidate: zero forecast as an error reference, plus all-event
   forward returns on the same matched sample; no conditional-selection claim.

## Walk-forward, purge and readiness

Fixed annual OOS folds are **2023, 2024 and 2025 UTC**, with an expanding
training window beginning 2019-01-01. Their dates are chosen from calendar
coverage, including the reported September 2020 OI start, not model outcomes.
There is no substituting a better year, a random split or a 2026 historical
holdout. Fit each model once at January 1. Test candidates have original
decision times within that calendar year; a December target may end in the
next year only if the frozen 2019–2025 source contains its complete horizon.
Unobserved end-of-source targets remain UNKNOWN.

Training needs decision < test_start-14d, label_end < test_start and
label_available_at < test_start. Purge every train outcome interval touching
any test interval; use only earlier training, so no future training fold can
leak backward. The 14d pre-test embargo is retained despite the 7d primary
target. Join feature vintages as of the original decision. Train targets are
admitted only after full-horizon maturity. Test scores, normalization and
selection thresholds cannot use later outcomes or future-year score ranks.

Before any fitting, source/identity and frequency-only readiness must pass:

- Each fixed fold has at least 24 calendar months of documented common
  feature coverage, 50 mature complete training candidates and 20 mature
  complete members of the frozen spaced population; both directions have
  at least ten complete training candidates.
- Each fixed test fold has at least 20 feature-complete candidates with a
  source-supported horizon and at least five scorable 14d components.
- The combined fixed OOS set has at least 15 scorable 14d components and
  25 complete members of the frozen spaced population, with both directions
  represented in every fold. Target values are not examined to pass readiness.
- Missing/revision/PIT policy and exactly which archives are admitted are
  independently signed off; no synthetic receipts or retrospective imputation.

These minimums are conservative eligibility requirements, not a power
calculation or a guarantee of a precise result. If any fail, record
`BLOCKED_READINESS` without fitting, evaluating associations or choosing a
replacement window. The reviewer may change a proposed minimum before any
MOM-002 association/score inspection, with a new version and stated rationale.

## Dependence, inference and counts

Intervals are [decision_time, cutoff+7d] for primary dependence and
[decision_time, cutoff+14d] for the maximum inherited sensitivity horizon.
Touching intervals share a connected component. Report
`overlap_components_7d` and `overlap_components_14d` on the entire 354-event
population, admitted training sets and matched OOS sets. Component identities
on the fixed full population are retained when an event is missing; report
both total and scorable components. Canonical full-population counts are
**128 at 7d and 47 at 14d**, using the inherited five-minute decision offset.
Muse's 117 at 7d uses intervals that start at cutoff instead: it connects
eleven boundary contacts exactly seven days apart. That alternate clock
convention is reported separately and does not replace the primary
decision-time convention. Neither component count is stochastic
independence. The 107-event global cooldown population is a conservative
view and an upper bound on independent opportunities, not an estimated
effective N. Do not compute a single fake precise `n_effective`.

Primary pooled OOS metrics use equal total weight per scorable 7d component,
with equal row weights inside the component. All benchmark comparisons are
paired on the same events. Report unweighted values and the exact frozen
spaced subset separately; neither can replace a failed primary metric.
Training weighting is computed from the mature prefix, as specified above;
full future component membership never enters model fitting.

Use a paired percentile cluster bootstrap, **2,000 draws, seed 20261002**,
resampling complete OOS component records with replacement and recomputing
the component-weighted statistic. Run it twice with fixed 7d and 14d cluster
definitions; preserve all observations, directions and paired model results
inside each sampled cluster. Repeated draws of a cluster receive distinct
replicate identities before weights are recomputed, so duplicated components
are not accidentally merged. Both 95% intervals must pass the relevant gate.
Use the same draw identities across models/metrics. Percentile endpoints
are 2.5% and 97.5%, using the fixed linear-interpolated empirical quantile
convention. A constant forecast, degenerate denominator or undefined
statistic is a failure, not omitted from the successful draws: place it at
negative infinity in the ordered lower-tail statistic, reporting any infinite
bound explicitly. Report undefined-draw fraction; >5% makes inference
`INSUFFICIENT_INFERENCE` and cannot pass. Confidence intervals are conditional
development diagnostics; they are not an assertion that clusters are truly
independent. No raw-row t statistic or alternative bootstrap can rescue a
failed gate. Report the spaced view's point metrics alongside these intervals.

## Metrics, causal score budget and economic sanity

Freeze **weighted Pearson correlation**, not a choice between Pearson and
rank correlation. Freeze weighted MSE skill `1 - MSE_A+B / MSE_comparator`.
All pooled errors/correlations use the identical matched OOS sample.
Spearman, alternative loss functions and alternate targets are not gates.

For score buckets, freeze the training score 1/3 and 2/3 weighted quantiles
at each fold origin, using the inverse weighted empirical CDF. Assign OOS
events to those frozen bins, retaining ties in the lower bin. Report each
bin's count, mean y and mean signed log return. No test-score terciles or
test-outcome bucket boundaries are allowed.

Economic selection uses **only the original 107-event spaced population**.
At each fold origin, freeze the 75th percentile of model scores on admitted
spaced training candidates, giving those spaced scores equal weight. Select
an OOS spaced candidate only when its
score is strictly above that threshold. Freeze an annual alert cap of
`floor(0.25 * count of admitted spaced training candidates in preceding 12m)`.
Process candidates chronologically and stop at that cap; a zero cap creates
zero alerts, not an exception. This is a causal top-quarter budget; it never
selects the best future-year scores. Report cap, alerts, unused budget and
ties. B1/Tier A use their own training thresholds and the identical cap. B0
uses deterministic every-fourth admitted spaced event in time order, capped
identically; report its actual count, with no cherry-picked offset.

An alert's net return is `d * log(P_close[t+7d] / P0) - 0.004`, charging a
40bp round-trip log-return hurdle. Also report the inherited extra-4h-close
entry-delay net return and an 80bp stress, neither as alternative primary.
This is an unleveraged descriptive forward-return check, not executable PnL.
MAE is the worst adverse direction-aligned hourly excursion / S over the
same complete horizon and with the inherited first-hour exclusion. Retain
every selected event; no stop-loss, success filter or ex-post-leg selection.

Economic gate comparisons use the arithmetic mean per alert, with paired
cluster draws retaining each model's selections and each benchmark's counts.
Report total return, mean, exposure/count and concentration together so a
different realized alert count cannot be disguised as budget parity. Draws
with zero alerts make that comparison undefined; apply the 5% rule above.

## Frozen pass/fail criteria

All gates below are required. Thresholds are proposed practical floors,
chosen without fitting or feature/target association inspection; none is a
power theorem. A reviewer must accept their severity before scoring.

| Gate | Required result |
| --- | --- |
| Primary information | pooled weighted OOS Pearson r >=0.10; its 95% lower bound >0 under both 7d and 14d bootstrap |
| Incremental information | pooled MSE skill versus Tier A >=5%; its 95% lower bound >0 under both bootstraps; MSE skill versus B0 >=5% and versus B1 >=0 |
| Spaced consistency | Pearson r >0 and MSE skill versus Tier A and B0 >=0 on the exact complete OOS members of the frozen spaced population |
| Fold consistency | r >0 and MSE skill versus Tier A >0 in all three fixed annual test folds; report both directions separately |
| Score monotonicity | all three frozen bins nonempty; pooled weighted mean y strictly increases low→middle→high; upper-minus-lower mean y has 95% lower bound >0 under both bootstraps |
| Economic evidence | at least eight OOS A+B alerts, at least two per fold and two per direction; mean 40bp-net signed log return >0 and 95% lower bound >0 under both bootstraps; incremental mean net return versus Tier A and B0 >0 |
| Adversity | selected normalized MAE median <1 S and 90th percentile <2 S; use the fixed linear-interpolated empirical quantile convention |
| Robustness | after removing each OOS year in turn, and separately after removing the five most influential 14d components, r >0, incremental Tier A MSE skill >0 and mean selected 40bp-net return >0 |
| Concentration | largest year <=50%, largest 14d component <=25%, and five largest 14d components <=60% of total positive selected net-return contributions; zero positive contribution fails |

For influence removal, rank 14d components by absolute contribution to the
paired pooled squared-error improvement of A+B over Tier A; ties break by
component's first decision timestamp. Remove the first five and recompute
all specified point metrics, without refitting or reselection. This is an
adversarial robustness diagnostic, never a rule for dropping training or
losing candidates. Leave-one-year-out means remove that year's frozen OOS
records and recompute metrics; it does not train on future years. Direction,
fold and interval definitions remain fixed. Stress/secondary figures cannot
replace a failed gate, and no best-metric selection is permitted.

Pass is `HISTORICAL_PASS_PENDING_PROSPECTIVE_CONFIRMATION` only if every
readiness and inferential gate passes. Any failed or undefined inferential,
predictive, incremental, economic or robustness gate is
`STOP_CANDIDATE_BTC_LINE_CLOSED`. A descriptive historical pass still needs a
new independently approved prospective confirmation contract; the current
shadow log validates causal receipt/parity and contains no MOM-002 forecasts.
Collection cannot quickly overcome the original rare-positive power problem.

## Review and execution lock

The reviewer must not be a designer of this contract. The approval record
must identify reviewer, date, reviewed commit, source assumptions, population/
feature identities, exact target, model/loss, folds, weighting, budget,
bootstrap and every gate. Approval or requested changes must precede any
MOM-002 fitting, feature/outcome association inspection, forecast generation
or gate evaluation. A design-team read-through is not independent approval.

Every pre-score requested change gets a new version and rationale, followed
by renewed independent review. The first authorized scoring run must preserve
code/data/contract hashes, every fold artifact, all UNKNOWN reasons and all
failed gates. There is one family/model/target packet and no hyperparameter
search. The terminal commitment above remains binding across revisions.
**Current disposition: `PENDING_INDEPENDENT_REVIEW`; scoring is prohibited.**
