# Momentum experiment ledger

Registration precedes outcomes. Historical failures do not disappear when
this directory changes. See EVIDENCE_AUDIT.md (audit in progress).

| ID | Kind | Contract | State | Predictive trials |
| --- | --- | --- | --- | --- |
| MOM-000 | Non-predictive census | event contract v1, BTC 2019–2025 | REGISTERED | 0 |
| MOM-DATA-001 | Source/PIT investigation | 1h archive integrity, 4h aggregation | REGISTERED | 0 |
| MOM-001 | Conditional prediction | below, contingent registration | NOT_ADMITTED_PENDING_CENSUS | 0 |

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

## Pre-outcome source clarification, MOM-DATA-001

Before any census score: verified archives contain missing hours and one
nonstandard close timestamp. Parser now retains raw bytes, excludes that
incomplete bar with its row hash, and exposes gaps. This implements the
registered incomplete-history/UNKNOWN policy; no mathematical barrier,
candidate, sample gate or horizon was changed. Zero predictive trials consumed.
