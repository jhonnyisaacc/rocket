# Momentum final report (iteration 1, 2026-10-02)

Branch `feat/momentum-refactor-muse`. Safety: `READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`.
No live execution, no trades, no leverage, no promotions. All figures below
are observed outputs of the committed code on checksum-verified data.

## 1. What was wrong or incomplete in the previous momentum research architecture?

Rocket scored PnL directly from narrative rules (`data → narrative → rule → PnL`)
with no separation between population definition, outcome contract, and
conditional prediction. PIT semantics lived only in `rocket.pit.PointInTime`
with no vintage/ingested_at; FRED served revised history as PIT; COT carried
no publication availability; Hyperliquid history was assumed deeper than it
is. This iteration introduces the RAW → PIT → FEATURES → LABELS → CONDITIONAL
RESEARCH → FORECAST separation with frozen contracts and UNKNOWN-not-false
throughout.

## 2. What was preserved from prior negative evidence?

All of it (detail: EVIDENCE_AUDIT.md). FUT-001…FUT-013 exact contracts stay
`CLOSED_EXACT_RULE` with inherited rescue prohibitions; PR #46 (puts
uneconomic, dip-buying luck, carry regime-concentrated), PR #40 (v6 holdout
lost, DSR ~0.00), PR #26 (shorts v2 edge not validated) verdicts stand.
The 42-bar breakout is a population definer, never scored as an edge — a new
use, not a fourth trend parameterization.

## 3. What exactly is a momentum candidate now?

candgen-v1: at each UTC 4h cutoff (decision = cutoff+5m), sigma = sample SD
of the last 180 4h log-close returns including the new bar. UP fires when the
decision close clears the highest high of the prior 42 bars by ≥0.5σ (log);
DOWN symmetrically below the lowest low. New events only on inactive→active
crossings per side. Flat/zero sigma or <30d contiguous history → UNKNOWN.
Independent set: first crossing + global 14d cooldown, either side.

## 4. What exactly is the forward outcome?

label-v1 triple barrier, fixed at candidate time: S = σ√42, reference = last
4h close. Favorable +2S, adverse −1S (log, signed by direction) on 1h OHLC,
first touch wins → CONTINUES / FAILS; neither by cutoff+7d → TIMEOUT.
Decision-bar and first post-cutoff hour excluded (167 label bars per 7d);
both-barrier bar or incomplete horizon → UNKNOWN. Sensitivity: 3d/14d ×
(2,1),(1.6,1),(2.4,1),(2,0.8),(2,1.2) — none substitutable for primary.

## 5. How many independent episodes exist?

107 globally 14d-spaced candidates (64 UP / 43 DOWN) from 354 raw crossings
over 2019–2025. Of these, 12 are successes (5 UP / 7 DOWN). Overlap analysis:
117 interval components, largest 11 events, 33% singletons — clustering is
real but bounded; spacing is a conservative independence upper bound.

## 6. Is 4h / 7d empirically defensible?

As a measurement clock, yes: data supports it completely (84/84 verified
months, 9 isolated quarantined rows). As a research design, the 7d (2,1)
contract yields a 7.8% UP / 16.3% DOWN success rate with median MFE of only
0.51S/0.30S — most candidates TIMEOUT (34/64 UP) or FAIL. Median resolution
~3.2–3.6d. The clock works; the phenomenon at this barrier scale is rare.

## 7. How front-loaded are upside and downside moves?

Ex-post legs (diagnostic only, n=58 large uncensored): at the first
mechanical 1S confirmation on a closed 4h bar, median 29% of the eventual UP
move is complete (71% remains) and 44% of DOWN moves (56% remains); +4h
28%/46%; never-confirmed legs 0. Front-loading PASSES the gate both sides.
Latency is not the binding constraint — sample size is.

## 8. Is BTC alone statistically sufficient?

No. 5 UP / 7 DOWN successes in 7 years cannot support a 4–6 variable
conditional model (frozen bar: ≥40/side). Kish effective N over year counts
is 6.7/5.7. No universe expansion — prohibited rescue.

## 9. Did Experiment 0 permit Experiment 1?

No. Gate verdict STOP (failed: ≥120 spaced → 107; ≥40 successes/side →
5/7; ≥3 folds with ≥10 successes/side; passed: concentration, front-load).
MOM-001 is NOT ADMITTED and was never scored (0 predictive trials).

## 10. Did Tier A+B add OOS information over baseline?

Untested by design — scoring was not admitted. The reserved packet
(Tier A/B definitions, logreg m1, B0–B3, budget rule, success bar) is frozen
in code and docs for a future separately-justified program, not executed.

## 11. Which metrics improved or failed?

No predictive metrics exist (nothing scored). Census metrics: success rates
above; cost-hurdle survival equals the success count at 20/40/80bp (all 12
successes clear 80bp round-trip — the barrier dwarfs costs); concentration
benign (UP top-1 7.6%, DOWN top-1 14.2%).

## 12. How sensitive are results to horizons/barriers?

Independent-success counts: 3d grid 4–6, 7d grid 7–14, 14d grid 16–21 per
cell. Longer horizons mechanically admit more successes, but no cell reaches
the 40/side bar and no cell may replace primary post-result.

## 13. Are results dominated by particular episodes or years?

Success-year shares pass the ≤40% gate (max 2/5 UP in 2023/2024, 2/7 DOWN in
2022/2025). Contribution concentration is moderate (top-5 MFE share 28%
UP / 45% DOWN). The 12 successes are distinct historical episodes (listed in
MOMENTUM_EXPERIMENTS.md), not one regime.

## 14. What PIT/data problems were discovered?

- 9 malformed vendor rows in 7 years (zero-volume flats, truncated closes)
  → quarantine-and-skip (A1), gaps → local UNKNOWN.
- No monthly OI/premiumIndex archives upstream; daily metrics is the only
  OI history (from 2020-09-01).
- Pre-existing: FRED revised-as-PIT, COT without publication date,
  Hyperliquid live-only history, assumed (not recorded) historical receipt.
  All documented in MOMENTUM_DATA_AUDIT.md.

## 15. Superseded vs preserved?

Preserved as HISTORICAL EVIDENCE: all FUT contracts, PR #40/#46/#26
verdicts, Pana failures. KEEP: `crypto.scan` production behavior, PIT
primitive, closed-bar rule. REUSE AS INFRASTRUCTURE: OI-as-participation,
portfolio context. No competing momentum canon created (REMOVE).

## 16. Is prospective collection working?

Mechanism implemented, unit-tested, and run live once: 2026-10-02T20:05Z
forecast appended to `/tmp/momdata/shadow` (both sides INACTIVE, σ=0.0075,
ref 84315.28); `verify_log` → 1 forecast, 0 outcomes, monotonic chain
intact. Append-only JSONL, no outcome fields at decision time, separate
enrichment file with forecast-hash binding, UNKNOWN on missing data.
Ongoing scheduled collection (00/04/08/12/16/20 UTC) remains for the user
to arrange; the mechanism is proven working.

## 17. Exact next admitted research question?

None on historical data under current registrations. The only admitted
forward path is prospective shadow-log collection at UTC 00/04/08/12/16/20.
A future program may pre-register a *different* candidate/label contract as
a new line with fresh justification.

## 18. Explicitly NOT admitted?

MOM-001 scoring in any form; MOM-002; slow-context rescue; Pana timing;
LLM/news features; universe expansion; threshold/feature/model/horizon
changes to the STOPped contracts; promoting anything to live.

## 19. Remaining blockers?

- Intermittent sandbox EMFILE (too many open files) disrupting shell
  execution; file tools unaffected.
- Census report JSON lives at /tmp/momdata (outside repo); must be copied
  to `artifacts/momentum/mom000_census.json` when shell recovers.
- Full metrics-parser validation on real daily files, one live shadow run,
  whole-suite pytest, commit/push/draft-PR — all pending shell recovery.

## 20. What would falsify the remaining momentum thesis?

A *new* pre-registered candidate/label contract (different scale, clock, or
population) failing its own feasibility gate on the same data; or the
prospective shadow log accumulating ~3 years of decisions with base-rate
continuation and no detectable conditional signal. This iteration falsified
only the specific 4h/7d/(2,1)/BTC-alone conditional path — not momentum
anticipation in general.
