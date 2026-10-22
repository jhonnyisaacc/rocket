# Momentum experiment ledger

Registration precedes outcomes. Historical failures do not disappear when
this directory changes. See EVIDENCE_AUDIT.md (audit in progress).

| ID | Kind | Contract | State | Predictive trials |
| --- | --- | --- | --- | --- |
| MOM-000 | Non-predictive census | event contract v1, BTC 2019–2025 | COMPLETE_STOP | 0 |
| MOM-DATA-001 | Source/PIT investigation | 1h archive integrity, 4h aggregation | COMPLETE | 0 |
| MOM-001 | Conditional prediction | below, contingent registration | NOT_ADMITTED_GATE_STOP | 0 |

## MOM-000 feasibility gates (frozen before results)

All required: ≥5 usable calendar years; ≥120 globally 14d-spaced fully
labeled candidates; ≥40 successful independent candidates **per direction**;
≥3 chronological annual test folds each with ≥10 successes per direction
and ≥24 preceding months for training; top year ≤40% of successes per side;
at least 50% of large diagnostic legs per side retain ≥50% of their move
at earliest 1 S confirmation plus 4h. These are conservative requirements
for a 4–6-variable model, not a power theorem. 40 positive episodes has
binomial SE ~8 percentage points near 50%; small lift would still need more.
Missing diagnostics cannot pass. Independence is bounded, not guaranteed.

If sample/latency fails: STOP conditional scoring in this PR. If source
verification fails: BLOCKED data; continue infrastructure and prospective
work. No daily substitution or universe expansion after viewing the result.

## MOM-001 reserved packet (not a scored or admitted trial)

Given passing MOM-000, freeze final schema and receipt audit before outcomes.
Tier A: signed 24h log return / (sigma sqrt(6)), short(6)/long(180) RV,
relative 24h spot volume / preceding 30d average. Tier B: signed trailing
24h realized funding sum, 24h log OI change, and spot/perp 24h quote-volume
ratio. Max six variables, no transformation search. Missing B leaves UNKNOWN;
no imputation from live endpoints, no dropping missing winners. If historical
OI/participation receipt coverage is inadequate, A+B is BLOCKED; any A-only
trial requires an explicit pre-result amendment, not a silent substitution.
B4 excluded unless a separate historical IV audit validates timestamps.

Model: logistic regression, train-only standardization, fixed L2=1,
intercept unpenalized; no tuning. Separate UP/DOWN intercepts, common feature
slopes if counts support it. B0 expanding train climatology; B1 logistic RV
ratio alone; B2 unfiltered candidate; B3 seeded block-null matching annual
frequency/cooldown (1000 shifts). Expanding training, annual OOS after ≥24m;
purge any train label interval touching test, apply 14d pre-test embargo.

Before scoring fix budget from census **frequency only**: floor(25% of
annual independent candidates), same for every detector, causal trailing
train score-quantile threshold frozen per fold, global 14d cooldown. Report
realized count as well as target; never select top future test scores. B2
budget comparator uses deterministic every-fourth candidate, B0 seeded
uniform thinning. Unfiltered B2 all-event figures also shown separately.

Success requires A+B versus Tier A AND B0/B1: positive OOS Brier/log-loss
skill and ≥1.25 precision lift, ≥20% episode recall; positive incremental
all-alert 40bp-net signed return with episode-bootstrap 95% lower bound >0;
same skill sign in ≥2/3 annual folds; calibration slope 0.5–1.5 and absolute
calibration error ≤0.10; median MAE <1 S and 90th percentile <2 S; survive
remove-top-five episodes, leave-year-out, and nonnegative incremental Brier
skill in every predeclared sensitivity cell. Report PR-AUC, direction among
large moves, false ignition, MFE/MAE, latency, concentration and detected
fraction; one pooled improvement is insufficient. 80bp cost is stress.

Failure closes this exact conditional path. No MOM-002, slow data, Pana,
news/LLM, or threshold/feature/model/horizon rescue. Amendments explicitly
consume the inherited research budget. Prospective final confirmation remains
mandatory even if all historical development gates pass.

## MOM-000 results (executed 2026-10-02, no model)

Source: Binance BTCUSDT spot 1h, 2019-01→2025-12, 84/84 monthly zips
checksum-verified, 9 quarantined rows out of 61,368 expected hourly bars
(isolated vendor anomalies: zero-volume flat rows and truncated close
times; gaps yield local UNKNOWN, never imputed). Report:
`artifacts/momentum/mom000_census.json` (reproduce with
`scripts/research/momentum_census.py`).

- Raw crossings: 354 (219 UP / 135 DOWN). Globally 14d-spaced
  independent: 107 (64 UP / 43 DOWN).
- Primary 7d (2,1) outcomes, independent set: UP 5 CONTINUES / 21
  FAILS / 34 TIMEOUT / 4 UNKNOWN (success rate 7.8%); DOWN 7 / 19 /
  15 / 2 (16.3%).
- Median MFE 0.51S UP / 0.30S DOWN; median MAE 0.78S / 0.84S; median
  end-of-window −0.12S / −0.48S. Median resolution ~3.2–3.6d.
- All 12 successes verified as real episodes (Sep-2019 breakdown, LUNA
  May-2022, FTX Nov-2022, Mar-2023 banking rally, Aug-2023 dump,
  Oct-2023 ETF rally, Feb-2024 ETF run ×2, Aug-2024 unwind, Feb-2025
  tariff dump, Jul-2025 ATH breakout, Oct-2025 dump).
- Year concentration of successes: no year above 40% (passes); Kish
  effective N over year counts 6.7 UP / 5.7 DOWN.
- Sensitivity successes (independent): 7d grid 7–14, 3d grid 4–6,
  14d grid 16–21. No cell was or will be substituted for primary.
- Ex-post legs: 122 legs, 58 large uncensored (30 UP / 28 DOWN).
  Front-loading at first 1S confirmation: median 29% of eventual move
  completed UP (71% remains), 44% DOWN (56% remains); +4h medians
  28% / 46%. Never-confirmed legs: 0. Latency is NOT the binding
  constraint.

Gate verdict: STOP. Failed: ≥120 spaced (107); ≥40 successes per
direction (5 UP / 7 DOWN); ≥3 annual folds with ≥10 successes per
direction. Passed: year concentration, front-loading retention.
Per the frozen rule, conditional scoring (MOM-001) is NOT admitted in
this PR. No threshold/feature/model/horizon rescue.

## MOM-DATA-001 results (executed 2026-10-02)

- Spot 1h: 2019-01→2025-12 complete, checksums pass.
- Perp 1h klines: 2020-01→2025-12 complete (72/72).
- Funding rate: 2020-01→2025-12 complete (72/72).
- Daily metrics (OI): available 2020-09-01→2025-12-31, absent before
  (first-avail established by bisection probe; full backfill not
  executed — unnecessary under the MOM-000 STOP).
- Tier B historical scoring would have been feasible on a gated
  2020-09+ sub-window with per-feature availability gating. Moot under
  STOP; recorded for any future separately-justified program.

## Amendments (implementation only, pre-result where it matters)

- A1: kline ingest quarantines malformed rows (recorded, skipped, gaps
  → UNKNOWN) instead of aborting the run. Forced by 9 real vendor
  anomalies; contract behavior (incomplete history → UNKNOWN)
  unchanged. Decided at first crash, before any outcome was viewed.
- A2 (interpretation, not a change): a 7d label window holds 167
  hourly bars, not 168 — the contracted excluded first post-cutoff
  hour ([cutoff+1h, cutoff+7d)). No threshold or horizon altered.
- A3 (parser plumbing, post-STOP, no contract change): `parse_metrics_csv`
  accepts the vendor's snake_case era (`sum_open_interest` /
  `sum_open_interest_value`, verified live on 2024-01-15: 288 intraday
  snapshots) in addition to camelCase; coin-denominated OI preferred so
  the 24h log change isolates positioning change. Tier B was never scored.
- A4 (bug fix, post-STOP, no contract change): `tier_b` compared
  midnight-ms day stamps against day-index integers, so `oi_change_24h`
  could never compute. Now compares in day-index units, last snapshot of
  a day wins. Covered by `test_tier_b_oi_change_wires_parsed_metrics_days`.
  Tier B was never scored; no result changes.
