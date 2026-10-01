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

## Family B — capitulation longs (variants B-*)
(none yet)

## Family C — funding/basis carry (variants C-*)
(none yet)
