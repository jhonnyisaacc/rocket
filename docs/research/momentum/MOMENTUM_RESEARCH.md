# Momentum research: canonical plan

Frozen before event outcomes or predictive scores, 2026-10-02. Safety is
`READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`. This document supersedes the old
staged futures scan as the roadmap for momentum *research*, without changing
its production behavior or promoting any strategy.

Question: can a deterministic BTC breakout candidate be classified early
enough to retain a large favorable move before excessive adversity?
Abstention is normal. A breakout defines the population; it is not an edge.

## Execute in order

1. Audit main and PRs #38/#40/#46/#26 and #28/#29/#31/#32/#35; retain exact
   failed rules, source limitations, contamination and unresolved roles.
2. Freeze candidate, label, census and feasibility gates in
   MOMENTUM_EVENT_CONTRACT.md and MOMENTUM_EXPERIMENTS.md. Commit this plan.
3. Acquire checksum-verified BTCUSDT spot **1h** archives, 2019-01 through
   2025-12 (fixed by calendar/long liquid coverage, not results). Aggregate
   complete UTC 4h bars. Audit timestamp units, gaps and revisions. Do not
   substitute daily bars or current live context. Keep 2026 out of historical
   scoring: already inspected elsewhere, neither clean nor needed here.
4. Implement small PIT observation, feature, candidate, label and fold
   primitives; immutable forecast and separate outcome records. Test causality,
   interval purging, unknowns, identity, boundary clocks and deterministic replay.
5. Execute Experiment 0 without a predictor. Report raw candidates, independent
   intervals, success/fail/timeout/unknown, excursions, costs, front-loading,
   diagnostic ex-post legs, year concentration, sensitivity and a gate decision.
6. Only if all feasibility gates pass, register the exact Experiment 1 feature,
   model, evaluation and budget packet before scoring. Otherwise record STOP
   or BLOCKED precisely. Do not change gates to admit a model.
7. Start prospective snapshots immediately when the deterministic collector
   exists. Schedule at UTC 00/04/08/12/16/20 with a 5-minute receipt allowance;
   save missing-data/late receipts as UNKNOWN. Append later outcomes separately.
8. Run the complete offline suite and lint for new code. Publish a coherent
   draft PR named feat/momentum-refactor-codex with a final report answering
   all twenty requested questions and exact reproduction commands.

## Architecture

Raw source bytes → PIT observations → features → candidate population and
future-only labels → conditional research → forecasts. Setup/expression/risk/
execution are future work. No LLM enters deterministic numeric decisions.
Use existing rocket.pit.PointInTime, not a competing eligibility definition.
Historical data is reconstructed under an explicit assumed close+5m market
availability; actual receipt is known only prospectively. Ingest time is never
backdated. Labels cannot enter features or forecast records.

## Research debt and authority

PR #38 suspended standalone futures families and demanded independently
reviewed successors. This user's explicit new program authorizes a descriptive
census and a gated conditional experiment, not FUT-014 or a resurrection of
failed trading rules. No fabricated independent approval is recorded. Preserve
its admission restrictions for those families. Historical walk-forward is
research development, not a pristine final validation. Final validation is
prospective; no ETH/SOL expansion or slow-context rescue is admitted.
