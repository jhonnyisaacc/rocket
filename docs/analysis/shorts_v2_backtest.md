# Shorts v2 backtest

Exploratory validation only. The sample is **nine ISM months** (December 2025
through August 2026 reports, decisions from 6 January 2026 through 16 September
2026). This is **not** proof of durable edge and is **not** a deployment
recommendation.

Assessment: **`PROMISING_BUT_INSUFFICIENT_SAMPLE`**

## Methodology

- Official ISM Manufacturing and Services contraction lists were taken from PR
  Newswire releases (`docs/analysis/data/ism_reports_2026.json`). Rank 1 is the
  most contracting industry.
- A month is eligible only after **both** series have published. Publication is
  the existing Rocket clock: first US business day (Manufacturing) or third
  (Services) at 10:00 America/New_York.
- Prices are Yahoo daily bars. `available_at` is approximated as NYSE session
  close. A decision before that close cannot see that session.
- Reported fundamentals and cash-flow quality use SEC company facts. Availability
  is the 10-K `filed` date. Restatements filed after the decision are excluded.
- 8-K / S-1 / S-3 catalysts use SEC submissions `filingDate`, kept only if filed
  in the prior 45 days.
- One entry per ticker per ISM month, at the close of the first trigger session.
- Short return is the negative of the underlying close-to-close return. Borrow,
  locate, and funding are UNKNOWN and are **not** in the P&amp;L.
- MAE uses session highs after entry; MFE uses session lows.

## Assumptions that are labeled, not hidden

### Backtest 1 — fixed reviewed universe

`config/industry_exposure.json` was reviewed in September 2026. Backtest 1 uses
that mapping in every historical month. That is a **fixed-universe research
test**, not a claim that Rocket already had those names in January 2026.

### Backtest 2 — strict PIT mappings

Only mappings with `reviewed_at` ≤ decision time. Those dates are 2026-09-08 and
2026-09-16. Result: **zero mapped names** in every backtest month.

### Estimate revisions

FMP current `/analyst-estimates` is not a vintage. No same-period snapshots exist
for January–August 2026. Variant C is therefore identical to Variant B and is
marked `HISTORICALLY_UNAVAILABLE`.

### Tokenized execution (Backtest B)

xStocks public listings and the current ONDO mint registry were observed at run
time. They are **not** applied to historical entries. No current snapshot had
`short_available=true`, so **zero** August 2026 research names are
`EXECUTION_ELIGIBLE`.

## Variants

| Variant | Rule | n | 5d short mean | 10d | 20d | 20d MAE median / max |
|---|---|---:|---:|---:|---:|---|
| A expanded | All contracting industries, expanded mapping, current ISM+breakdown+bearish 10-K gate | 47 | −0.61% | −0.35% | −0.34% | 6.6% / 28.8% |
| A sparse | Same gate, original 12 tickers only | 10 | +2.24% | +2.27% | +1.56% | 3.1% / 9.7% |
| B | Top-3 industries/series, relative &lt; 0 vs sector and SPY, same 10-K gate, 20d trigger | 40 | +0.84% | +0.67% | +0.13% | 5.6% / 39.6% |
| B −5% | Relative &lt; −5% | 27 | +1.20% | +2.25% | −0.02% | 4.6% / 50.0% |
| B retest | B plus failed retest required | 20 | +0.80% | +0.09% | −1.24% | 5.4% / 14.5% |
| C revisions | B; revisions historically unavailable | 40 | same as B | same | same | same |
| D catalyst | B, but TRIGGERED only if an 8-K/S-1/earnings-miss catalyst exists | 32 | +1.19% | +1.66% | +0.23% | 4.9% / 39.6% |
| E R/R ≥ 1.5 | B plus observed R/R ≥ 1.5 | 19 | +1.36% | +0.84% | +0.38% | 4.6% / 13.2% |
| E R/R ≥ 2.0 | B plus observed R/R ≥ 2.0 | 15 | +1.57% | +1.72% | +1.81% | 2.6% / 13.2% |
| E R/R ≥ 2.5 | B plus observed R/R ≥ 2.5 | 12 | +2.17% | +1.65% | +1.54% | 4.5% / 13.2% |
| Strict PIT | B with September 2026 mapping dates | 0 | — | — | — | — |

Win rates for A expanded were 58.7% / 53.8% / 57.9% at 5/10/20d with a 5d
profit factor of **0.74**. B’s corresponding win rates were 67.5% / 57.6% /
59.4% with a 5d profit factor of **1.74** and a 20d profit factor of **1.04**.

A sparse looks better than A expanded, but **n = 10**. That is the old
one-name-per-industry universe, not evidence that sparsity is an edge.

## Month-by-month (Variant B)

| Month (ISM reference) | Mfg top industries | Svc top industries | Mapped | Deterioration | WATCH | TRIGGERED |
|---|---|---|---:|---:|---:|---:|
| 2025-12 | apparel; wood; textile | management support; professional services; agriculture | 14 | 7 | 5 | 4 |
| 2026-01 | textile; wood; nonmetallic mineral | other services (unmapped); transportation; management support | 12 | 9 | 5 | 3 |
| 2026-02 | apparel; furniture; petroleum | retail; arts; transportation | 14 | 11 | 8 | 7 |
| 2026-03 | plastics; furniture; food | retail; agriculture; public admin (unmapped) | 13 | 8 | 7 | 4 |
| 2026-04 | wood; petroleum; food | agriculture; real estate; retail | 18 | 12 | 9 | 6 |
| 2026-05 | wood | real estate | 6 | 4 | 3 | 2 |
| 2026-06 | paper; furniture; wood | agriculture; educational; management support | 15 | 8 | 6 | 3 |
| 2026-07 | chemical | agriculture; other services (unmapped); health care | 9 | 6 | 6 | 4 |
| 2026-08 | wood; chemical | agriculture; construction; management support | 15 | 10 | 8 | 7 |

December 2025 Manufacturing had **15** contracting industries. The old path
would have tried to map all of them; v2 keeps three. August 2026 Manufacturing
had only two contracting industries, so v2 correctly uses two rather than
forcing three.

## What improved

- **Universe coverage.** December 2025 mapped 45 names with the expanded file
  versus 7 with the original 12 tickers. August 2026 ISM no longer collapses to
  a handful of one-name industries.
- **Relative weakness.** Moving from A expanded to B flipped 5-day mean short
  return from −0.61% to +0.84% and 5-day profit factor from 0.74 to 1.74, with
  a slightly lower median 20-day MAE (6.6% → 5.6%).
- **ISM as universe selection.** Top-3 per series is enough to populate a
  watchlist every month in this sample. WATCH exists without requiring the
  breakdown on day one.

## What did not improve / should not be implemented from this sample

- **Failed retest as a required trigger.** n drops to 20 and 20-day mean short
  return goes to **−1.24%**. Keep it as an optional flag, not a gate.
- **Estimate revisions.** No honest history. Do not backfill from today’s FMP
  consensus. Persist snapshots going forward.
- **Hardcoded R/R ≥ 2.0.** The 20-day mean looks better (+1.81%) but n is 11–15.
  That is curve-picking on nine months. Leave R/R as context; do not freeze a
  threshold.
- **Strict historical mappings.** Cannot be reconstructed before September 2026.
  Do not pretend Backtest 1 is a perfect PIT simulation of the mapping file.
- **Tokenized short overlay on history.** Current listings are long-biased and
  `short_available` is UNKNOWN. Zero names are execution-eligible today.
- **Switching the live default off `ism_simple`.** 20-day B vs A is +0.13% vs
  −0.34% with max MAE **worse** in B (39.6% vs 28.8%). Apparel names can dominate.

## Industries

Useful in B (mean 20d short, n still tiny): professional services, management
support, plastics, retail, transportation.

Harmful in B: apparel (PVH/HBI), agriculture, arts/entertainment, real estate,
educational services.

Those industry means are **one-to-four observations**. They are attribution,
not a sector model.

## Factor attribution example

`PVH`, ISM apparel rank 1, 2025-12 report, first trigger 2026-01-07 close:

- relative vs sector −14.3%, vs SPY −12.7%
- EPS revision UNKNOWN (no vintage)
- cash-flow quality deteriorating; reported EPS growth −1.9%
- catalyst `EARNINGS_MISS`
- 20d breakdown true, failed retest true
- regime `SHORT_HOSTILE`
- R/R 0.49 (no 1.5 filter)
- 5d short +0.62%, 20d short +2.12%, 20d MAE 4.9%

Full triggered rows are in `docs/analysis/data/shorts_v2_backtest.json`.

## Data limitations

- Yahoo session-close availability is an approximation.
- SEC User-Agent policy required a contact-style header; facts are public 10-K
  XBRL, not a paid fundamentals vendor vintage.
- FMP/Massive keys were absent in this run.
- No borrow fees, days-to-cover, funding, or depth.
- Mapping knowledge timestamp is September 2026.
- Unmapped ISM buckets remain unmapped (`other services`, `public administration`).
- Sample is nine months in a generally expanding 2026 manufacturing cycle after
  December 2025 contraction. Results are regime-specific.

Machine-readable summary: `docs/analysis/data/shorts_v2_backtest.json`.
