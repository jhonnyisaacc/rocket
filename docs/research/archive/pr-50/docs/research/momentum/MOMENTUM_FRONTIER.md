# Momentum frontier

Frozen categories, updated only by recorded results or amendments.
Negative findings are preserved, not reinterpreted.

## Established

- `rocket.pit.PointInTime` is the single PIT eligibility definition.
  Nothing in this program replaces it.
- Completed-bar-only filtering (`closed_bars`) is the bar-timestamp
  standard. Momentum 4h aggregation follows it.
- Triple-barrier outcome contract v1 and 42-bar / 0.5σ candidate
  generator are frozen in MOMENTUM_EVENT_CONTRACT.md.
- Feasibility gates and the MOM-001 reserved packet are frozen in
  MOMENTUM_EXPERIMENTS.md. Registration precedes outcomes.

## Rejected exact rules (CLOSED; rescue prohibited)

From PR #38 FAMILY_AUDIT through FUT-013, PR #46, PR #40, PR #26:

- Standalone trend/time-series momentum (FUT-001/002/003, hist. daily
  50-close break): compounding/cost/replication gates failed.
- Spot/perp basis tails, COT standalone, aggregate order flow,
  funding-tail rebound, order-book pressure, macro/dollar linkage,
  wallet-close rules, liquidation reversal, BTC→alt lead/lag transfer.
- Systematic BTC put insurance (economically negative), dip-buying
  automation (luck-indistinguishable), v6 crash-timing promotion
  (holdout lost), ISM shorts v2 promotion (edge not validated).
- Pana/Cryptopana full-stack and direct ZONE entry as traded rules.

None of these may be rescued by changing thresholds, horizons, signs,
assets, or adding a confirmation. The 42-bar breakout here is a
**population definer**, never scored as an edge; that is a new use,
not a rescue.

## Resolved by MOM-000 (2026-10-02)

- 4h/7d leaves enough remaining move after realistic detection lag:
  YES for the diagnostic bound (median 71% remains UP / 56% DOWN at
  first 1S confirmation). Latency is not the binding constraint.
- BTC alone supplies enough independent episodes for a 4–6 variable
  conditional model under the (2,1) contract: NO (5 UP / 7 DOWN
  successes in 7 years). No ETH/SOL expansion — prohibited rescue.

## Unresolved (legitimate open questions, pre-registered only)

- Conditional role of OI/funding/participation **given** a breakout
  candidate (MOM-001 Tier B): NOT ADMITTED — gate STOP, never scored.
  Standalone/sign-transfer uses remain failed; the incremental
  given-candidate question remains untested and stays pre-registered
  only for a future separately-justified program.
- Conditional role of short-vs-long realized volatility and relative
  volume (Tier A): NOT ADMITTED — same gate STOP.

## Blocked by default

- MOM-001 scoring in any form (gate STOP). Re-admission needs a new
  pre-registered program with fresh justification, not an amendment.
- Tier B historical backfill beyond coverage bounds (moot under STOP;
  coverage recorded: perp/funding from 2020-01, metrics/OI from
  2020-09-01).
- B4 (implied-vol baseline) until a historical IV audit validates
  timestamps and PIT availability.
- ALFRED/vintage macro features; COT as predictor; Cava/X/news/LLM
  historical features; ISM/macro/Pana/wallet/order-book/lead-lag
  inputs.
- Any MOM-002, slow-context rescue, Pana timing study, or universe
  expansion built on the STOPped MOM-000 result.

## Permitted next (only through gates)

1. Prospective shadow-log collection (collector exists; schedule at
   UTC 00/04/08/12/16/20). This is the primary forward path: the only
   honest validation left is prospective.
2. A future program *may* pre-register a different candidate/label
   contract as a new experiment line with fresh justification — it may
   not amend MOM-000/MOM-001 post-result.

## Prohibited rescue

Slow context, Pana, LLM/news, universe expansion, threshold/feature/
model/horizon changes, or a MOM-002 created to rescue the STOPped
MOM-000/MOM-001. Amendments consume inherited research budget and are
recorded; the multiple-testing clock does not reset because the
directory changed.

## Disposition of prior concepts

- `crypto.scan` staged funnel + `setup_validation` entry zones: KEEP
  (production behavior unchanged; not the research population).
- FUT-001…FUT-013 exact contracts: HISTORICAL EVIDENCE (closed).
- PR #40 v6 timing, PR #46 put/capitulation/carry trades, PR #26
  shorts v2 promotion: HISTORICAL EVIDENCE (verdicts preserved above).
- OI-as-participation, portfolio context: REUSE AS INFRASTRUCTURE
  (mechanism open, needs validated base + fresh plan).
- PRE_IGNITION/IGNITION/EXPANSION stage labels: NOT APPLICABLE
  (rejected unless data compels; single forward outcome used).
- Competing "canonical momentum strategy": REMOVE (no second canon;
  this program is research, not a strategy line).
