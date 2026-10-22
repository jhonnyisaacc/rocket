# Evidence audit: what prior Rocket research established

Completed 2026-10-02 from branch contents and PR bodies (no re-scoring;
all figures below are quoted from the cited sources). Failures are
preserved as evidence. Each entry distinguishes the rejected exact rule
from any unresolved conditional role.

## PR #38 — canonical crypto futures foundation (draft, unmerged)

`research/crypto-futures-strategy`. Family audit through FUT-013;
historical PRs #28/#29/#31/#32/#35 remain evidence with superseded next
steps. Admission gate: distinct mechanism, PIT observability, cheap
falsifier, fresh chronology, family budget/stop rule, independent review
(proposer cannot self-approve). All family budgets zero. No FUT-014.

| Family | Registered result | State |
|---|---|---|
| FUT-001/002/003 trend persistence | 20bp arithmetically weak-positive but compounding-negative; 60-day control failed 2022 replication; Bybit transfer cost-sensitive | CLOSED_EXACT_RULE |
| Historical daily 50-close breakout (PR #32) | failed validation | CLOSED_EXACT_RULE |
| FUT-004 spot/perp basis tails | both-year gross robustness failed | CLOSED_EXACT_RULE |
| FUT-005 COT standalone | 2023 gross/net failed; 2024 arithmetically positive, compounding-negative, Q1-concentrated | CLOSED_EXACT_RULE; context OPEN_MECHANISM |
| FUT-006 quarter-hour order flow | pooled −2.53bp gross | CLOSED_EXACT_RULE |
| FUT-007 funding tails | sample + economic gates failed | CLOSED_EXACT_RULE |
| FUT-008 order-book pressure | incremental/cost gates failed | CLOSED_EXACT_RULE |
| FUT-009 macro/dollar linkage | gross/incremental/net failed | CLOSED_EXACT_RULE |
| FUT-010/011 wallet closes | fee floor / incremental gates failed; causal front-end cohort unresolved | CLOSED_EXACT_RULE; cohort OPEN_DATA_GATE |
| FUT-012 liquidations | second-half incremental gate failed (August-dominated pooled positive) | CLOSED_EXACT_RULE |
| FUT-013 BTC→alt lead/lag | all four fee-floor cells failed | CLOSED_EXACT_RULE |
| OI participation (Bybit audit) | no directional experiment; PIT/source limits (340 active days missing OI, stale GST OI) | OPEN_MECHANISM |
| Portfolio context | no standalone/incremental trial; depends on validated base | OPEN_MECHANISM |

Rescue prohibitions (nearby horizons, buffering, side/coin/quarter
slices, sign/threshold/lag swaps, conditional post-failure scoring) are
inherited unchanged. Reopening needs a demonstrated material bug or
independently motivated, structurally distinct mechanism with review.

Relation to this program: the 42-bar vol-normalized breakout is a
**population definer**, never scored as an edge — a new use, not a
fourth trend parameterization. Tier B reuses OI/funding families only in
the unresolved conditional role (given a candidate), which FUT-004/006/
007 did not test.

## PR #46 — BTC derivatives (draft, unmerged)

Seven years of BTC, 12m/3m walk-forward, single 2026-01→2026-09 holdout,
≤5 free params, ±20% sensitivity, deflated Sharpe, next-bar fills.

- Puts as insurance (16 variants): NO EDGE. 11–18%/yr cost, lost to
  naked hold OOS and in holdout. Planned ~$940 hedge: SKIP.
- Buy-the-capitulation longs (8 variants): positive but
  luck-indistinguishable (DSR P=0.00 over 10 trials, n=3 holdout legs).
- Funding carry (4 variants): statistically real (DSR P=1.00) but
  regime-concentrated — two thirds of lifetime carry from 2021; ~1%/yr
  since 2023, holdout −0.55%. Watchlist item, not a trade.

## PR #40 — macro market-check (draft, unmerged)

v6 frozen after 43 walk-forward experiments. In-sample Sharpe edge over
equal-weight; stitched headline Sharpe 1.24 vs 1.06 — but deflated Sharpe
~0.00 against a 1.73 benchmark: return edge indistinguishable from
mining luck. Clean 2026-06→2026-09 holdout lost on both axes (Sharpe
0.44 vs 0.49, deeper drawdown). Verdict: hold equal-weight; v6 at most a
cushion with eyes open. Puts sleeve: −3.8% in sample, dropped.

## PR #26 — ISM shorts v2 (open, unmerged)

Expanded PIT mapping + relative-weakness filter flipped the 5d mean
positive vs the expanded gate but did not beat the sparse A0 baseline;
`core_edge_assessment` and `live_v2_edge_assessment` both
EDGE_NOT_VALIDATED. Catalyst requirement yields zero trades (catalysts
stay explanation, not gate). Tokenized-short eligibility: none of the
research names executable historically.

## Architecture gaps found on main (this audit)

- `rocket.pit.PointInTime`: no vintage/revision identity; momentum
  observations add explicit vintage + ingested_at.
- `providers/fred.py`: revised CSV served as PIT (`as_of` = latest
  observation). Not PIT; no ALFRED rebuild here; Exp1 avoids revisions.
- `providers/cftc.py`: `release_date: None`; `as_of_date` is the Tuesday
  position date while publication is Friday (~3d lookahead if used as
  availability). COT excluded from Exp1.
- `providers/hyperliquid.py`: live-only candles/funding (500-row cap),
  no 2019–2025 history. Prospective collector, not historical source.
- `workflows/crypto.py`: 4h setup is a 6-bar HH/HL structure with entry
  zones (Pana-adjacent staging), kept for production behavior; the
  momentum census uses a separate, simpler population definer and does
  not change scan behavior.
- Historical reconstruction on main can silently use live context
  (current mappings/universe/parameters). Momentum tests assert
  post-decision mutation invariance.

## Contamination statement

BTC history inspected by the above programs is research-development
data. 2026 is not a pristine holdout (PR #46 exposed most of its path;
PR #40's tuning universe reaches 2026-05). Walk-forward here is honest
development; final validation is prospective via the shadow log.
