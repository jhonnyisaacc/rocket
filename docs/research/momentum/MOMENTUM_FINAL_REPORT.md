# Momentum final report — 2026-10-02

**MOM-000 failed its pre-registered sample gate. MOM-001 did not run.** No
predictive information, calibrated forecast, strategy or trading edge was
established. Rocket remains `READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`.

The plan/contract were committed in **3272afc before outcomes**, from updated
main **09d7150** on `feat/momentum-refactor-codex`. Implementation/source audit
was committed in **c6458e3 before scoring**. Unmerged research PR stacks were
not inherited. Historical negatives remain evidence, with exact commit links
in [EVIDENCE_AUDIT.md](EVIDENCE_AUDIT.md).

## What was implemented

- `rocket.momentum.core`: shared PIT eligibility with explicit availability,
  ingestion and vintage, strict bar clocks/aggregation, feature identities,
  crossings, deterministic spacing, future-only triple barriers and causal
  fold purge/embargo primitives.
- `source`: 84 checksum-verified BTC spot hourly ZIPs, timestamp-unit
  normalization, malformed-row/gap retention and source receipt manifest.
- `census`: deterministic event/outcome/episode diagnostics and admission gate,
  independent population, year/contribution concentration and all 15 fixed
  horizon/barrier sensitivity cells; no predictor.
- `shadow`, `collect`, `enrich`, `status`: append-only forecasts, separate mature
  outcome appends, raw-source blobs, commit/tree/schema identities, receipt
  checks, retries returning originals and coverage/integrity audit.
- Normal FRED/OpenBB history now explicitly advertises current reported
  history, historical_pit=false, unknown release availability/vintage.
- Canonical docs, README consolidation, 29 momentum/PIT tests and offline CI.

## Primary census

All returns/excursions below are **log-price fractions**, shown ×100. They
are descriptive forward outcomes, not executed strategy PnL or leverage.

61,300 valid hourly observations → 15,307 complete 4h bars → **11,943 eligible
decisions** → **354 crossing events** → **107 globally 14d-spaced candidates**.
There are **47 connected 14d overlap components** across raw crossings.
Only **101** spaced candidates have complete/unambiguous primary labels.
Row counts do not establish independent N. Spacing supplies an upper bound
for disjoint label intervals; stochastic independence is unresolved.

| Primary 7d statistic | UP | DOWN |
| --- | ---: | ---: |
| Raw crossings | 219 | 135 |
| Raw crossing successes (overlapping) | 30 | 22 |
| Spaced candidates | 64 | 43 |
| Fully labeled spaced candidates | 60 | 41 |
| CONTINUES | 5 | 8 |
| FAILS | 21 | 21 |
| TIMEOUT | 34 | 12 |
| UNKNOWN | 4 | 2 |
| Spaced candidates/year | 9.14 | 6.14 |
| Success base rate among known labels | 8.3% | 19.5% |
| Mean signed 7d return | -0.35% | -3.21% |
| Mean return after additional 4h close delay | -0.18% | -3.43% |
| Median full-window MAE | 5.05% | 6.78% |
| Median full-window MFE | 3.85% | 3.72% |
| Mean after 4h delay and 40bp hurdle | -0.58% | -3.83% |
| MAE normalized S, median / p90 | 0.78 / 1.75 | 1.06 / 2.74 |
| MFE normalized S, median | 0.51 | 0.48 |
| Median time to barrier/timeout | 167.9h | 120.9h |

Cost hurdles at 20/40/80bp and the extra 4h close delay are all in CENSUS.json.
They omit funding/borrow/size/liquidity and cannot establish feasible futures
execution. MAE and negative means supply no basis for leverage.

## Front-loading and concentration

Ex-post directional-change segmentation yields **33 large UP and 32 large
DOWN legs**. At earliest closed-bar 1 S confirmation, median fractions
already consumed are **35.9% / 41.3%**. After another 4h: **36.5% / 42.3%**;
8h: **36.1% / 44.3%**; 12h: **36.7% / 45.1%**. The fraction retaining at
least half at confirmation+4h is **78.8% / 68.8%**, passing the registered
latency diagnostic. At first same-direction causal crossing, median consumed
is **49.2% / 49.0%**; candidates occur in 32/33 and 30/32 legs, misses counted
fully consumed. Median peak lead among detected legs: **184h / 104h**.

**These are optimistic, ex-post conditional diagnostics.** Anchors/endpoints
are selected using subsequent reversals. Median leg durations are **380h UP
/ 286h DOWN**; only 8 UP and 11 DOWN legs finish within 7d. Therefore the
latency pass does not prove a timely 7d forecast or anticipated direction.
`remaining_momentum_at_signal` on realized successes can look artificially
attractive; all-candidate outcomes above are the economic evidence.

UP spaced successes: 2023=2, 2024=2, 2025=1. DOWN: 2019=1, 2022=2,
2023=1, 2024=1, 2025=3. The largest year accounts for 40% / 37.5%.
Year-count Kish N is **2.78 / 4.00**, a concentration diagnostic rather than
an episode count. Full-window positive-MFE concentration has Kish weights
**31.41 / 18.55**; top five candidates contribute **28.3% / 40.9%** of MFE.
After removing the five largest MFE candidates, mean signed return worsens
to **-1.66% / -5.19%**. No significance is inferred from these small cohorts.

## Sensitivities and gate

| Horizon / primary barriers | UP successes | DOWN successes |
| --- | ---: | ---: |
| 3d | 2 | 4 |
| 7d | 5 | 8 |
| 14d | 9 | 10 |

Across all predeclared barrier cells, counts range **2–10 UP / 4–12 DOWN**.
No cell approaches forty successes per side. Upper/lower changes are
descriptive sensitivities, never replacement contracts. The 14d primary cell
has 54/41 complete side labels. No year has ten successes in either side,
let alone three annual folds with adequate training chronology.

Usable calendar coverage and oracle latency pass. The 120-complete-candidate
gate, both 40-success gates and both three-fold gates fail. Even all overlapping
crossings contain only 30 UP / 22 DOWN successes. The verdict is
**STOP_INSUFFICIENT_FEASIBILITY**, not universal impossibility of anticipation.
This closes scoring on the registered BTC population in this PR.

## Answers to the delivery questions

1. **Previous architecture:** mixed setup/context/entry gates and outcome/portfolio
   accounting; no canonical rare-event conditional outcome or immutable numeric
   forecast journal. #38 improved family governance, which is preserved.
2. **Negative evidence:** exact failed trend/breakout/quintile, COT, Pana, macro
   timing, puts, carry limitations and FUT-004–013 failures are retained with
   distinctions between exact rule rejection, unresolved role and data limit.
3. **Candidate:** inactive→active close breakout beyond prior 42 4h-bar high/low
   by 0.5 trailing 180-return sigma. Global 14d spacing is outcome-independent.
4. **Outcome:** frozen S=sigma sqrt(42), favorable 2 S before adverse 1 S;
   first future-hour barrier wins; 7d timeout; gaps/two-hit ordering UNKNOWN.
5. **Independent episodes:** 107 interval-spaced candidate upper bound, 101
   known labels, 5/8 side successes; 47 raw overlap components. True effective
   independent N cannot be honestly reduced to a single proven number.
6. **4h/7d:** technically supported by hourly data; empirically insufficient
   for the intended predictor. Longer diagnostic legs do not validate 7d.
7. **Front-loading:** optimistic bound retains opportunity on many completed
   legs, but actual crossing occurs around halfway; conditional selection and
   horizon mismatch prevent treating that as skill.
8. **BTC sufficiency:** fails registered count/fold requirements; a small useful
   lift would need more evidence even if forty successes were reached.
9. **Experiment 1 admission:** no; sample gate failed.
10. **Tier A+B OOS improvement:** untested; zero predictive trials. Tier B
    historical receipt/coverage is also unverified.
11. **Metrics:** census counts/returns/excursions/latency/concentration measured;
    precision lift, PR-AUC, calibration, Brier/log-loss, model recall/direction
    accuracy and classifier robustness are **N/A, not zero or passed**.
12. **Sensitivity:** all fifteen frozen cells remain sample-insufficient.
13. **Dominance:** UP successes concentrated in 2023–2025; DOWN largest year
    2025. MFE is concentrated and top-five removal worsens negative means.
14. **PIT issues:** 68 missing/rejected hours, spot microsecond change, revised
    archives, absent old receipts, FRED current-history/vintage ambiguity,
    publication vs observation lags, limited COT/IV/OI/mapping histories.
15. **Disposition:** operational readouts/infrastructure KEEP; old momentum
    roadmap SUPERSEDED; all historical contracts/results preserved. No old
    experimental runtime is ported; no deletion needed.
16. **Prospective:** real receipt captured and immutable/source integrity audited;
    heartbeat ACTIVE, six local daily slots; sustained scheduled coverage and
    real mature candidate enrichment are not yet observable at startup.
17. **Next admitted question:** collection completeness and causality on the
    frozen prospective population, with later immutable outcomes.
18. **Not admitted:** model trial, asset/clock/barrier/search expansion, MOM-002,
    slow-context/Pana/news/LLM rescue, leverage/options or live execution.
19. **Blockers:** sparse successful episodes; causal Tier B/IV history; authentic
    old receipts; prospective scheduler uptime and passage of real future time.
    No required architecture/test/documentation work is left blocked.
20. **Falsifiers:** insufficient fresh independent episodes, failed latency or
    receipt coverage, no incremental equal-budget OOS skill/calibration,
    concentration, MAE/costs consuming economics. Future predictor admission
    needs its own independent review and frozen prospective power/period plan.

## Reproduction and verification

From the checkout after installing `.[dev]` (Python 3.12+):

```bash
python -m rocket.momentum.source .rocket/momentum/raw docs/research/momentum/SOURCE_MANIFEST.json
python -m rocket.momentum.census .rocket/momentum/raw docs/research/momentum/results
python -m rocket.momentum.status .rocket/momentum/shadow
pytest -m 'not integration' -ra
ruff check rocket/momentum tests/momentum
git diff --check
```

Source acquisition requires public network access. Large raw ZIPs remain
ignored; manifest URLs/hashes permit download. Raw archive revisions after
this iteration must be compared with the manifest rather than accepted as
the same vintage. `EVENTS.json` includes all crossings, labels and spacing
membership; `EPISODES_DIAGNOSTIC.json` is diagnostics only. `CENSUS.json` binds
contract/source/scorer hashes. Feature v1→v2 correction is explicitly ledgered;
label fingerprint and candidate counts/gate replayed unchanged. Deterministic
full census replay is checked on the final committed code.

Local verification: **610 passed, 1 integration test deselected** on Python
3.14.1; 29 momentum/PIT tests included. Ruff 0.16.6 and whitespace pass.
Offline CI additionally runs the full suite on Python 3.12, no market data
acquisition or historical scoring. Remote CI status is recorded in the PR.

Prospective runtime code and the initial public startup audit are available;
future observations cannot be manufactured to complete a test today. The
configured collector remains UNTRAINED and does not emit trade decisions.

Canonical references: [research plan](MOMENTUM_RESEARCH.md),
[event contract](MOMENTUM_EVENT_CONTRACT.md), [data audit](MOMENTUM_DATA_AUDIT.md),
[ledger](MOMENTUM_EXPERIMENTS.md), [frontier](MOMENTUM_FRONTIER.md),
[prospective operations](PROSPECTIVE_OPERATIONS.md).
