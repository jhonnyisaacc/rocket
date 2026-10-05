# BTC derivatives edge: backtest report

Question: does any BTC derivatives rule have a robust, out-of-sample edge?
Three families tested separately. Headline result: no family earns a live
trade signal. Carry is statistically real but economically marginal and
regime-thin; dip-buying expectancy is positive but insignificant; puts as
insurance lose out of sample and in holdout.

## Data (free sources only)

| Series | Source | Coverage |
|---|---|---|
| BTC daily spot | Binance `api.binance.com/api/v3/klines` | 2019-01-01 to 2026-10-01 (2831 rows) |
| Perp funding | Binance `fapi.binance.com/fapi/v1/fundingRate` | 2019-09-10 on (7735 rows) |
| Perp funding x-check | Bybit `api.bybit.com/v5/market/funding/history` | recent 200 rows only (API ignores date params) |
| DVOL index | Deribit `deribit.com/api/v2/public/get_volatility_index_data` | 2021-04-01 on (2010 rows) |
| Options calibration | Deribit `get_instruments` + `ticker` | live book 2026-10-01 |
| Events | `federalreserve.gov/monetarypolicy/fomccalendars.htm` + election dates | 45 FOMC (2021+) + 3 elections |

No 4h bars (daily sufficed), no OKX/Hyperliquid funding, no free CPI/payrolls
machine calendar (FOMC + elections only), no historical basis series. Clipped
at 2026-09-30; holdout is 2026-01-01 to 2026-09-30, evaluated once.

## Pricing and costs (approximation, labeled)

Pre-2021-04 vol: 30d realized vol. From 2021-04: DVOL/100 x 1.10 skew
haircut (validated live 2026-10-01: DVOL 36.4 vs 15-17% OTM put IVs ~40.3,
ratio 1.11). Fills at mid + 3% half-spread + 0.03% Deribit taker fee,
next-bar only. Longs: spot/1x with taker fees + funding while in perps.
Carry: taker fees both legs + slippage + funding earned/paid. Crash-time
liquidity is worse than modeled; stated as caveat.

## Protocol

12-month train / 3-month test walk-forward, 24 windows 2020-01-01 to
2026-01-01, argmax train score per window, stitched OOS headline. At most 5
free params per family; round motivated thresholds. Every variant logged in
`docs/crypto/EXPERIMENTS.md` (18/10/6 trials for A/B/C incl. sensitivity).
Sensitivity +-20%, best-episode-removed, deflated Sharpe on stitched OOS
daily, next-bar fills throughout. Full-sample descriptives below include the
holdout window and are context only; selection and headlines never touched
2026-01-01+.

## Family A — puts as insurance (16 variants, NO EDGE)

Candidates: monthly 35d roll (A-1), quarterly 100d (A-2r), semiannual 180d
(A-6), stress 10%-DD entries (A-10), cheap-vol trailing-25th (A-13),
pre-event 30d (A-8). Blind rolls cost 18-28%/yr for roughly a wash
(monthly 35d: ~28%/yr, hedged DD -99.7% vs naked -76.6% — worse). The two
best full-sample variants both buy +13pp of DD reduction for 11-22%/yr of
bleed (stress-10%: 22.4%/yr, 5/7 crash wins; cheap-vol-25th: 12.0%/yr, 5/7
wins). Cheap-vol with a full-sample percentile was a lookahead bug; fixed to
a trailing-252-print rank (pinned by no-lookahead tests). Single-leg
analogues of the planned hedge (one 180d 15% OTM put, 90d before each known
trough, WITH lookahead): only 3/7 paid at trough, 1/7 held to expiry.

Per-crash drawdown reduction, champion A-13 (pp; + means hedge helped):

| Crash | Naked DD | Hedged DD | Reduction |
|---|---|---|---|
| 2020-03 covid | -50.0 | -50.0 | 0.0 |
| 2021-05 deleverage | -52.8 | -52.5 | +0.3 |
| 2022-05/06 LUNA | -59.0 | -34.6 | +24.4 |
| 2022-11 FTX | -18.3 | -7.9 | +10.4 |
| 2024-08 yen | -16.6 | -16.3 | +0.3 |
| 2025-04 tariffs | -21.8 | -15.7 | +6.0 |
| 2026 decline | -50.6 | -55.5 | -4.9 |

Walk-forward: cheap-vol selected 19/24 windows. Stitched OOS: combined
9.73x vs naked 9.99x at 18.0%/yr cost, avg test DD-win +3.8pp. Holdout:
3 entries, 10.5%/yr, hedged DD -44.2% vs naked -39.5% — worse.
Sensitivity 20/25/30th pct: identical (-63.3% at 11-12%/yr). Ex-LUNA rerun:
still +13.3pp at 11%/yr (needs a second crash to justify). DSR on the OOS
overlay: Sharpe -0.19, benchmark 0.63, P(skill) 0.00 over 18 trials.

## Family B — buy-the-capitulation longs (8 variants, NOT SIGNIFICANT)

Drawdown entries work per-trade: dd-30% 32 legs +7.1%/leg (B-1), dd-40%
21 legs +10.4%/leg (B-2), dd-25% 39 legs +7.1%/leg, equity 8.88x (B-8).
Funding <=-0.05%/day fires 5 times since 2019 (+19.1%/leg, rare). DVOL
spike-then-fade loses (-1.0%/leg, dropped). Exits barely matter (no-trail,
wide-stop, 180d time stop all ~6x). But 6-9x leg-compounded equity trails
~22x buy-hold on idle capital, and legs miss fast V-crashes (2024-08,
2025-04 fired zero times at -30%) while buying falling knives (LUNA -33.7pp
across 3 legs, contained by the stop, never avoided).

Per-crash leg totals, B-8 dd-25% (entry inside window, pp):

| Crash | Legs | Total | Note |
|---|---|---|---|
| 2020-03 covid | 3 | +48.6 | best episode |
| 2021-05 deleverage | 4 | +12.2 | |
| 2022-05/06 LUNA | 3 | -33.7 | falling knife, stop-contained |
| 2022-11 FTX | 1 | +29.0 | |
| 2024-08 yen | 1 | +29.5 | dd-25 catches what dd-30 missed |
| 2025-04 tariffs | 1 | +23.5 | |
| 2026 decline | 6 | +3.8 | grind, no rebound yet |
| Outside crashes | 20 | +162.8 | edge is broad dip-buying, not one episode |

Walk-forward: no dominant pick (dd40 9, fund 6, dd30/dd25 4 each windows).
Stitched OOS: 15 legs, 53% win, +3.76%/leg, 1.51x. Holdout (L-dd40): 3
legs +10.6/-14.2/+29.8 (avg +8.7%/leg, n=3 proves nothing). Sensitivity
20/25/30%: +7.3/+7.1/+7.1%/leg — stable. Ex-covid: +6.31%/leg over 36.
DSR: Sharpe +0.33, benchmark 0.53, P(skill) 0.00 over 10 trials —
positive but luck-indistinguishable.

## Family C — funding carry (4 variants, MARGINAL)

Short-perp/long-spot when funding is extreme, flip at 3-10bp/day.
Full sample: +23 to +31pp total (~+3-4%/yr), max DD -0.01 to -0.12; fees eat
~half the gross carry. Hold-7d beats flip-daily (+31 vs +23pp). But the
carry lives in one regime:

| Year | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| C-4 return (pp) | -0.5 | +5.8 | +21.0 | -0.8 | -0.0 | +3.5 | +0.0 | +0.0 |

Walk-forward: f3bp 11, f5bp-h7 8, f10bp 5 selections; stitched OOS +30.2pp
(+4.5%/yr, max DD -2.55). Holdout (C-f3bp-h1): -0.55%. Sensitivity 4/5/6bp:
flat (+0.29/+0.31/+0.30). Ex-2021 rerun: +1.03%/yr. DSR: Sharpe +2.61,
benchmark 0.44, P(skill) 1.00 over 6 trials — statistically real, but two
thirds of lifetime carry came from 2021 bull-market funding. Capacity:
extreme prints coincide with wide spreads; venue risk (FTX 2022) is not
theoretical; post-2023 prints are thin.

## Recommendation for the planned ~$940 put hedge: SKIP

The plan (~$940 on Mar-2027 $70k + Dec-2026 $72k, ~13-16% OTM) is ~1.1% of
one BTC at spot $84,692 — a fraction of the full-cover analogues tested,
which cost 11-12%/yr per BTC (~$9-10k/yr) for +13pp of drawdown reduction in
the best variant, underperform naked out of sample (9.73x vs 9.99x), and
worsened the holdout drawdown. Perfectly timed single-leg analogues paid
only in slow grinding crashes (LUNA 2.9x); fast crashes recovered past the
strike before expiry (0x in 4/7 episodes; the 2026-decline analogue paid
0x). If tail cover is wanted anyway as consumption rather than investment:
wait for a 10% drawdown-from-high stress entry, buy 90d+ tenor 15% OTM, size
it as a spend-you-accept-losing, and do not roll monthly (28%/yr bleed).

## Verdict (plain English)

We tested sixteen put-hedge designs, eight dip-buying rules, and four
funding-carry trades on seven years of Bitcoin data, grading each on fresh
data it had never seen plus a final untouched nine-month holdout. Nothing
earns a live signal. Put insurance costs 11-18% a year and still lost to
simply holding Bitcoin, even before the wider crash-time spreads you would
really pay. Dip-buying wins slightly more often than it loses, but the
statistical test says that could easily be luck, and it sits out long
stretches while Bitcoin itself rose twenty-fold. Funding carry is the only
statistically real edge, yet almost all of it came from 2021's overheated
bull market; since 2023 it pays about 1% a year, which venue risk and effort
swallow. So: skip the $940 hedge, do not automate dip-buying, and treat
carry as a watchlist item, not a trade. The daily check now carries a
read-only Perps readout (`crypto perps`: vol bucket, dip state, funding
state, each with a changed-vs-yesterday flag) so these answers update with
new data instead of new opinions.
