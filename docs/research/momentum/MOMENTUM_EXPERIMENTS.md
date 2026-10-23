# Momentum experiment ledger

Registration precedes outcomes. Historical failures do not disappear when
this directory changes. See EVIDENCE_AUDIT.md and REPLICATION_REPORT.md.

| ID | Kind | Contract | State | Predictive trials |
| --- | --- | --- | --- | --- |
| MOM-000 | Non-predictive census | event contract v1, BTC 2019–2025 | STOP_INSUFFICIENT_FEASIBILITY | 0 |
| MOM-DATA-001 | Source/PIT investigation | 1h archive integrity, 4h aggregation | COMPLETE_GAPS_RETAINED | 0 |
| MOM-001 | Conditional prediction | below, contingent registration | NOT_ADMITTED_SAMPLE_GATE_FAILED | 0 |
| MOM-REPL-001 | Descriptive replication | pinned PR49/PR50, same source bytes | COMPLETE_STOP_PRESERVED | 0 |
| MOM-DATA-002 | Tier B / CFTC source investigation | source catalogs/checksums/release lineage | COMPLETE_READINESS_ONLY | 0 |
| MOM-DATA-003 | Future source contract | interval-based metadata proposal | PROPOSED_NOT_ACTIVATED | 0 |
| MOM-002 | New continuous information proposal | mom002-continuous-v1 | PENDING_INDEPENDENT_REVIEW | 0 |

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

Before any census score: the initial source clarification singled out a nonstandard
close timestamp. The committed manifest actually lists nine excluded rows
and 59 absent hours. Parser retains raw bytes, excludes those nine under the
frozen rule with row hashes, and exposes gaps. A nonstandard close timestamp
alone is not a proved invalid price; see the later source-contract finding. This implements the
registered incomplete-history/UNKNOWN policy; no mathematical barrier,
candidate, sample gate or horizon was changed. Zero predictive trials consumed.

## MOM-000 first result / admission decision

Primary census: 354 crossings, 107 globally spaced candidates, 101 fully
labeled (UP 60, DOWN 41), only **5 UP and 8 DOWN successes**. The explicit
component counts are 128 at 7d and 47 at 14d under decision-time intervals. Sample gates fail;
MOM-001 is **NOT_ADMITTED_SAMPLE_GATE_FAILED**, predictive trial spend **0**.
No A-only substitute, alternative classifier or MOM-002 is run.

## Implementation correction, after census and before prediction

Relative-volume denominator had a one-bar offset versus the immediately
preceding 174 bars. Corrected with an explicit boundary test; feature schema
advanced from price-market-v1 to price-market-v2. No predictive feature was
scored. Candidate/label mathematics and the census gate are unchanged; replay
must preserve counts and label fingerprint. The original v1 startup forecast
remains immutable with its code commit. New forecasts also preserve candidate
crossing objects and code-tree hashes; no old forecast is rewritten. This is
an implementation correction, not another scientific trial or outcome rescue.

## Explicit later authorization: reconciliation and MOM-002 proposal only

The user subsequently requested a separate MOM-002 continuous information
proposal. This supersedes the earlier automatic-successor prohibition only
for writing that proposal, not for scoring it or reopening MOM-001.
[MOM_002_PROPOSAL.md](MOM_002_PROPOSAL.md) freezes a new target, low-capacity
model, exact features/clocks, paired benchmarks, causal folds/budget and all
gates. State is PENDING_INDEPENDENT_REVIEW, with no scorer/fitting/association
inspection or independent approval. Existing descriptive end returns were
already exposed; history remains contaminated development data.

[Replication](REPLICATION_REPORT.md) restores definitive comparison to the
frozen contract: 354/107 candidates, 5 UP/8 DOWN successes, identical label
fingerprint and STOP. Orientation and MFE conventions explain Muse's label
and excursion differences; clock/horizon conventions explain components.
Quarantine, leg and Tier B audits are descriptive/source work, not predictive
trials. Correcting prospective crossing parity after UNKNOWN affects new
code-identified snapshots only and preserves both original startup forecasts.

If an independently approved MOM-002 later fails any frozen predictive,
incremental or economic gate, this candidate-based BTC line closes. No
MOM-003, COT/macro/Cava/X/news/Pana, ETH/SOL, replacement generator/horizon,
model complexity or feature-transform rescue. This is a research STOP, not a
universal claim that momentum anticipation is impossible.
