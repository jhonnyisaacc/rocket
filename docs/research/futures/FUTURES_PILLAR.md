# Futures pillar

Status: authoritative directional research doctrine, consolidated 2026-09-30.
Read the [constitution](../RESEARCH_CONSTITUTION.md), this pillar,
[frontier](FUTURES_FRONTIER.md), [family audit](FAMILY_AUDIT.md), then the
[admission gate](EXPERIMENT_ADMISSION.md). Historical next steps have no authority.

## Goal and product boundary

The eventual goal is a validated crypto-perpetual directional strategy whose
`rocket crypto scan --json` contract could express `ENTER_LONG`, `ENTER_SHORT`,
`WAIT` or `NO_TRADE`, with causal forecast, asset, context, setup, trigger,
invalidation, objectives, risk, unresolved conditions and evidence. This PR
establishes research foundations only. No validated directional edge or
`ENTER_*` policy exists; execution requires separate authorization.

The current production funnel and direction summary are legacy behavior,
not a validated strategy. Research code under `research/futures` is offline
analysis and source tooling; it does not replace scan or execution behavior.
Binance history provides deeper research coverage; Hyperliquid is the intended
execution/forward-shadow venue. Cross-venue transfer must be measured.

Cross-venue carry requires simultaneous long/short legs, multiple collateral
and margin accounts, funding and conversion accounting, outage/transfer and
liquidation rules, and paired execution. It is
`STRUCTURAL_BUT_OUT_OF_CURRENT_PRODUCT_SCOPE`; the [carry source audit](CARRY_SOURCE_FEASIBILITY.md)
preserves source findings but grants no directional experiment. A separate
operator-approved product pillar is required before carry scoring. Likewise,
aggregate OI counts both sides: source-ready OI alone has no trading direction.

## Evidence and architecture

Forecast → opportunity ranking → derivatives/regime context → entry timing →
risk/portfolio → decision. Forecast and sizing are evaluated separately.
Incremental features require an independently viable base and an ablation on
matched opportunities; fewer trades do not establish better information.

The [family audit](FAMILY_AUDIT.md) is the current family-level conclusion;
[experiment ledger](EXPERIMENT_LEDGER.md) retains frozen designs, amendments
and result fingerprints, and [component ledger](COMPONENT_LEDGER.md) records
roles. FUT-001/002/003 did not establish robust trend expectancy. FUT-004 through
FUT-013 closed their exact registered rules after failed cheap gates. Historical
Pana/ZONE/TheoryV2/cross-sectional/daily-break outcomes remain visible in
[historical evidence](HISTORICAL_EVIDENCE.md). Neither failures nor unresolved
broader mechanisms imply permission for another parameterization.

The original futures tape preserves delistings, zero-volume/flat rows and
missing observations. Held cessations were bounded before scoring rather than
silently excluded. Minute-index settlement envelopes remain provisional;
current-catalog completeness, actual venue costs and executable fills remain
acceptance limits. Source audits demonstrate measured coverage, not alpha.
The 2026 final holdout is untouched; only a frozen promotion candidate with
constitution-authorized independent review may access it.

## Admission and promotion

Every successor requires the written nine-part [admission decision](EXPERIMENT_ADMISSION.md)
before registration and independent review before outcome scoring. Default
family grant is one cheap outcome trial, followed by suspension. Two failed or
nonrobust material attempts suspend ordinary continuation; another trial needs
new independent evidence, reviewed reopening and operator approval of the
exception. All present family budgets are zero. A different experiment ID,
paper, horizon or threshold does not change this state.

A cheap gate requires causal observability, source feasibility, costs, sample
and chronological controls, concentration/uncertainty checks and a simple
baseline. Survivors require separately admitted replication, walk-forward,
multiple-trial accounting, intended-venue overlap, a frozen untouched holdout
and prospective shadow before promotion. A risk throttle or ex-post side/coin
slice cannot validate a forecast. Preserve failures and dependent trial counts.

Current strategy state: `RESEARCH`. Current authorized work is consolidation,
offline verification of existing results and CI hygiene. After this foundation
pass, successor PRs may propose reviewed admissions; none is selected here.
