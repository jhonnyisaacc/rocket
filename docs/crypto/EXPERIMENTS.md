# BTC derivatives research — experiment log

Walk-forward: 12-month train, 3-month test, stepped forward from 2019-01-01.
Headline: stitched out-of-sample result. Final untouched holdout:
2026-01-01 to 2026-09-30, evaluated ONCE at the end. Each family has at
most 5 free parameters (round, economically motivated). Every variant is
logged here, including failures. Next-bar fills only; realistic fees,
funding, spreads. STOP at stable WF across 3 iterations or ~30 variants
per family.

Variant count: 0.

## Data sources (all free, documented)

- BTC spot daily 2019+: Binance public klines (`api.binance.com`, no key).
  4h klines from the same endpoint if intra-crash detail is needed.
- Perp funding: Binance `fapi` fundingRate (8h), Bybit v5 funding history,
  OKX funding-rate-history, Hyperliquid `fundingHistory` (POST info).
  Cross-check median across venues; report venue disagreement.
- Vol: Deribit DVOL from 2021 (`get_volatility_index_data`; empty early
  windows fall back to documented gaps, never interpolated silently).
  Pre-2021 vol = realized vol from spot. Options priced Black-Scholes on
  DVOL/realized with a skew haircut, labeled APPROXIMATION everywhere.
- Macro context: the existing panel (VIX, HY spreads, 30y, DXY).
- Events: FOMC decision dates 2021+ (45, scraped from federalreserve.gov
  minutes filenames; 2019-2020 not on the page) plus US general elections
  2020/2022/2024. CPI and payrolls have no free machine-readable calendar
  found; pre-event tests use FOMC plus elections, documented gap.

Coverage gaps (documented, not silently filled): Binance funding starts
2019-09-10 (perps did not exist before); DVOL starts 2021-04 (pre-2021 vol
is realized vol from spot); Bybit's API ignores date params and returns
only the newest ~200 prints, so it is a recent cross-check, not history;
FOMC 2019-2020 absent (page shows 2021+). Spot runs to 2026-10-01; engines
clip analysis at 2026-09-30.

## Family A — puts as insurance (variants A-*)

Pricing: Black-Scholes on DVOL (realized vol pre-2021-04) x1.10 skew,
mid + 3% half-spread, 0.03% Deribit taker fee. Skew validated live
2026-10-01 (DVOL 36.4 vs 15-17% OTM put IVs 40.3, ratio 1.11); half-spread
observed ~1.6% on those strikes. Live calibration: BTC $84,692,
Mar27-70k mid 0.0316 ($2,676), Dec26-72k mid 0.0178 ($1,507).

- A-0 (FAILURE, discarded): DVOL fed as percent-points not decimals plus
  swapped BS iv/rate args. Protection looked nearly free (0.36%/yr).
  Caught by leg inspection, pinned by test_pricing.py.
- A-1 monthly roll, 35-day 15% OTM: 92 legs, ~28%/yr of notional
  (at 3% half-spread), hedged full-sample DD -99.7% vs naked -76.6%.
  Monthly 1-month insurance is ruinous at BTC vol levels.
- A-2 quarterly roll, 100-day 15% OTM: 92 legs (monthly decisions!),
  ~82%/yr — mis-specified (overlapping 100-day cover). Redo with
  quarterly decisions before judging longer tenors.
- A-2r quarterly decisions (spacing 90, tenor 100, 15% OTM): 32 legs,
  ~25%/yr, hedged DD -77.2% vs naked -76.6%. Helps LUNA (+24.5pp) and
  2021-05 (+14.7pp), hurts or flat in 5 of 7 crashes.
- A-3/A-4 (FAILURES, mis-specified): monthly decisions with 100/180-day
  tenors stack 3-6x concurrent cover (56%/121%/yr). Spacing must match
  tenor; added spacing_days, applies to every trigger.
- A-5 quarterly 100-day 20% OTM: 32 legs, ~18%/yr, hedged -75.7% vs
  -76.6%. Cheaper, pays only in mega-crashes (LUNA +22.7pp).
- A-6 semi-annual 180-day 15% OTM: 16 legs, ~20%/yr, hedged -80.7%.
  Helps 2020-03 (+22.5pp) and LUNA (+21.1pp), hurts 2021-05/FTX/2026.
- A-7 cheap-vol (DVOL <=25th pct, 90-day 15% OTM): 11 legs, 6.5%/yr,
  zero reduction in every big crash. Adverse selection confirmed: vol is
  cheap exactly when no crash comes.
- A-8 pre-event (7d before FOMC/election, 30-day 15% OTM): 46 legs,
  14.1%/yr, best windows +2.4pp (2021-05) and +2.0pp (LUNA), worse
  elsewhere. Crashes are not scheduled.

- A-9 single-leg analogues (one 180d 15% OTM put bought 90d before each
  crash trough, WITH lookahead): only 3/7 paid at trough (covid 2.4x,
  2021-05 1.9x, LUNA 2.9x); FTX 0.7x, yen 0.9x, tariffs 0.5x, 2026 0x.
  Held to expiry only LUNA paid (2.7x). Even perfectly timed, premium in
  vs trough value out is ~1.2x gross, ~0.4x if held to expiry. Timing plus
  fast recoveries defeat the strike.
- A-10 stress 10% DD from 90d high (90-day 15% OTM): 27 legs, 22.4%/yr,
  hedged DD -63.5% vs naked -76.6% (+13.1pp), 5/7 crash wins. Real
  protection, ruinous price.
- A-11 stress 15% DD (90-day 15% OTM): 23 legs, 24.6%/yr, hedged DD -77.4%
  vs naked -76.6% (no win). Waiting for deeper stress mistimes cover.
- A-12 stress 10% DD (60-day 15% OTM): 38 legs, 27.8%/yr, hedged DD -86.7%
  (WORSE than naked). Shorter tenor under stress buys realized-vol peak.
- LOOKAHEAD FIX: cheap-vol ranked DVOL against the full sample. Replaced
  with a trailing-252-print percentile (min 63 prints), pinned by two new
  no-lookahead tests. All A-7 numbers are superseded by A-13..A-15.
- A-13 cheap-vol trailing <=25th pct (90-day 15% OTM): 17 legs, 12.0%/yr,
  hedged DD -63.3% vs naked -76.6% (+13.3pp), 5/7 crash wins. Causal timing
  costs more and protects more; still a 12%/yr bleed for +13pp.
- A-14 cheap-vol trailing <=15th pct (90-day): 15 legs, 9.8%/yr, hedged DD
  -79.0% (no win). Stricter cheapness mistimes cover.
- A-15 cheap-vol trailing <=25th pct (60-day): 25 legs, 12.0%/yr, hedged DD
  -76.3% (no win). Shorter tenor wastes the signal.

## Walk-forward round 1 (WF-1): 12m train / 3m test, 24 windows
2020-01-01 to 2026-01-01, argmax train score per window, stitched OOS.

- Family A candidates P-monthly35/P-quarterly100/P-semi180/P-stress10-90/
  P-cheap25-90/P-preevent. Selected P-cheap25-90 in 19/24 windows.
  Stitched OOS: combined 9.73x vs naked 9.99x, cost 18.0%/yr, avg test
  DD-win +3.8pp. Insurance loses to naked out of sample: 18%/yr buys
  3.8pp of drawdown reduction. NO EDGE as protection.
- Family B candidates L-dd30/L-dd40/L-dd25/L-fund/L-dvolfade. No dominant
  pick (dd40 9, fund 6, dd30 4, dd25 4, dvolfade 1). Stitched OOS: 15 legs
  (only 3/24 windows had >=2 legs), 53% win, +3.76%/leg, equity 1.51x.
  Positive expectancy survives OOS at half the full-sample size. THIN.
- Family C candidates C-f3bp-h1/C-f5bp-h1/C-f10bp-h1/C-f5bp-h7. Selected
  f3bp 11, f5bp-h7 8, f10bp 5 times (f5bp-h1 never). Stitched OOS: +30.2pp
  total, +4.5%/yr, max DD -2.55. Small persistent edge, threshold choice
  barely matters. SURVIVES.

## Robustness round (WF-2): sensitivity, best-episode-removed, DSR

Sensitivity (+-20% on champion threshold, full sample):
- A cheap-vol 20/25/30th pct: cost 11.1/12.0/11.6%/yr, hedged DD -63.3%
  in all three. Stable, stably bad. (2 new trials: A=18 total.)
- B drawdown 20/25/30%: avg-leg +7.3/+7.1/+7.1%, n=44/39/32,
  equity 13.14/8.88/6.01x. Expectancy rock-stable; equity scales with
  trade count. (2 new trials: B=10 total.)
- C funding 4/5/6bp hold-7d: total +0.29/+0.31/+0.30, max DD <=-0.02.
  Flat. (2 new trials: C=6 total.)
Best-episode-removed:
- A-13 ex-LUNA (window excised, rerun): cost 11.0%/yr, hedged DD -63.3%
  vs naked -76.6% (FTX +10.4pp win remains). Verdict unchanged: pays
  11%/yr for +13pp, needs a second crash to justify.
- B-8 ex-covid (drop 3 best legs arithmetically): +6.31%/leg over 36 legs
  vs +7.07% with covid. Edge is not one episode.
- C-4 ex-2021 (year excised, rerun): +1.03%/yr vs +4%/yr with 2021.
  Two-thirds of lifetime carry came from the 2021 bull-market funding
  regime. DOWNGRADED to marginal ex-regime.
Deflated Sharpe on stitched OOS daily (Sharpe / benchmark / P[skill]):
- A overlay (combined-minus-naked): SR -0.19 / bench 0.63 / prob 0.00
  over 18 trials. Negative; no edge, definitively.
- B leg-equity: SR +0.33 / bench 0.53 / prob 0.00 over 10 trials.
  Positive but luck-indistinguishable. Thin, not significant.
- C equity: SR +2.61 / bench 0.44 / prob 1.00 over 6 trials.
  Statistically real, but regime-concentrated (see ex-2021 above).
Holdout champions (from WF selection frequency ONLY, never full-sample):
A=P-cheap25-90 (19/24 windows), B=L-dd40 (plurality 9/24), C=C-f3bp-h1
(plurality 11/24). Full-sample descriptives above saw holdout data and
are context only; selection and headlines never touched 2026-01-01+.

## Family B — capitulation longs (variants B-*)
- B-1 drawdown-30% (stop 15%, target 30%, 90d time stop, 20% trail):
  32 legs, 17W/15L, +7.1%/leg, equity 6.01x 2019-2026 (vs ~22x buy-hold).
  Exits: 12 target, 12 stop, 5 trailing, 2 time, 1 truncated.
- B-2 drawdown-40%: 21 legs, 13W/8L, +10.4%/leg, equity 6.10x. Deeper
  capitulation selects better, still far below buy-hold on idle capital.
- B-3 funding <= -0.05%/day: only 5 legs since 2019-09, 4W/1L, +19.1%/leg,
  equity 2.30x. Rare signal; episode-dependence check pending.
- B-4 DVOL spike-then-fade (80+, 5d): 10 legs, 3W/7L, -1.0%/leg, equity
  0.81x. Fading vol spikes loses; dropped unless WF disagrees.
- B-5 dd30 no-trailing: 29 legs, +8.1%/leg, equity 6.33x. Trailing adds
  little; plain stop+target is enough.
- B-6 dd30 wide stop 25% / target 50%: 26 legs, +9.2%/leg, equity 6.10x.
  Wider exits do not change the story.
- B-7 dd30 180d time stop: 31 legs, +7.1%/leg, equity 5.62x. Patience does
  not help; dead legs stay dead.
- B-8 dd25: 39 legs, 22W/17L, +7.1%/leg, equity 8.88x. Best so far; shallower
  trigger trades more without diluting expectancy.
- B-1 per-crash attribution (entry inside window): covid +38.8pp (3 legs),
  2021-05 +19.0pp (4), LUNA -33.7pp (3, falling knife), FTX +29.0pp (1),
  2024-08/2025-04 zero legs (never reached -30%), 2026 +9.3pp (6),
  outside-crashes +164.6pp (15 legs). Edge is broad dip-buying, NOT one
  episode; LUNA is the counterexample that the stop contains.


## Family C — funding/basis carry (variants C-*)

- C-1 extreme funding >=3bp/day flip, hold>=1d: 239 flips, funding earned
  +66pp, net total +29pp (~+3%/yr), max DD -0.12. Fees/slippage eat ~half
  the gross carry.
- C-2 threshold 5bp: 128 flips, net +23pp (~+3%/yr), max DD -0.04.
- C-3 threshold 10bp: 102 flips, net +13pp (~+2%/yr), max DD -0.03.
  Higher threshold, less carry harvested.
- C-4 threshold 5bp hold>=7d: 74 flips, net +31pp (~+4%/yr), max DD -0.01.
  Patience keeps the carry without the churn. Best so far.
