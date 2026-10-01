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
- Events: FOMC, CPI, payrolls, US elections/midterms (calendar file).

## Family A — puts as insurance (variants A-*)
(none yet)

## Family B — capitulation longs (variants B-*)
(none yet)

## Family C — funding/basis carry (variants C-*)
(none yet)
