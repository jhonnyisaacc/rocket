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


## Family C — funding/basis carry (variants C-*)
(none yet)
