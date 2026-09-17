# Shorts v2 backtest

Exploratory validation only. Nine ISM months (December 2025 through August 2026
reports; decisions 6 January 2026 through 16 September 2026). This is **not**
proof of durable edge and is **not** a deployment recommendation.

| Layer | Verdict |
|---|---|
| Infrastructure | **useful** |
| Core edge (A3 vs A0) | **`EDGE_NOT_VALIDATED`** |
| Live v2 edge (A6 vs A0) | **`EDGE_NOT_VALIDATED`** |
| Top-level `edge_assessment` | **`EDGE_NOT_VALIDATED`** (follows live A6) |

Coverage is not alpha. Beating only an expanded-universe baseline is not
enough. A0’s +2.3% five-day mean is a **ten-trade, WY-heavy book**, not a
production edge that v2 failed to beat by bad luck.

## Methodology

- Official ISM Manufacturing and Services contraction lists come from PR
  Newswire releases (`docs/analysis/data/ism_reports_2026.json`). Rank 1 is the
  most contracting industry.
- A month is eligible only after **both** series have published. Publication is
  the Rocket clock: first US business day (Manufacturing) or third (Services)
  at 10:00 America/New_York.
- Prices are Yahoo daily bars. `available_at` is NYSE session close. A decision
  before that close cannot see that session.
- Reported fundamentals and cash-flow quality use SEC company facts. Availability
  is the 10-K `filed` date. Restatements filed after the decision are excluded.
- 8-K / S-1 / S-3 filings use SEC submissions `filingDate`, kept only if filed
  in the prior 45 days. Generic items are **not** bearish.
- One entry per ticker per ISM month, at the first trigger. Multi-theme names
  (same ticker in manufacturing and services) remain **one trade** in P&amp;L,
  n, win rate, and MAE/MFE. Theme/industry tables attribute that same return
  to **every** contributing ISM theme. Theme attribution is non-additive.
- Default entry is `CLOSE_SIGNAL`. `NEXT_SESSION_OPEN` is reported separately.
- Short return is the negative of the underlying return. Borrow, locate, and
  funding are UNKNOWN and are **not** in the P&amp;L.
- MAE uses session highs after entry; MFE uses session lows.

## Assumptions that are labeled, not hidden

### Fixed-universe research test

`config/industry_exposure.json` was reviewed on 2026-09-08 and 2026-09-16.
Variants A0–A6 apply that mapping in every historical month. That is a
**labeled fixed-universe test**, not a claim that Rocket already had those
names in January 2026.

### Strict PIT mappings

Only mappings with `reviewed_at` ≤ decision time. Result: **zero mapped names**
in every backtest month.

### Estimate revisions

FMP current `/analyst-estimates` is not a vintage. No same-period snapshots
exist for January–August 2026. Revisions stay `HISTORICALLY_UNAVAILABLE`.

### Tokenized execution

xStocks, Kraken xStock perps, and Ondo perps were observed at run time. Spot
never implies a short. Kraken `openingDate` is `listing_at` only.
`available_at` equals `observed_at`. A February listing date on a September
snapshot does **not** prove March shortability. Historical
`EXECUTION_ELIGIBLE` requires `observed_at` ≤ decision time. No current
research name is `EXECUTION_ELIGIBLE`.

## Production baseline

**A0_PRODUCTION** is the original twelve-name sparse universe
(`CAT`, `NUE`, `DOW`, `WY`, `TXN`, `VLO`, `F`, `PEP`, `WMT`, `UPS`, `JPM`,
`GOOGL`) plus the live `ism_simple` gate: ISM contracting, 20-session
breakdown, bearish reported fundamentals. Cheap valuation remains a veto.

This is the closest match to the **pre-expansion** Rocket shorts book. It is
not a claim that live ISM discovery still uses only those twelve names today.
Live `rocket ism --research-companies` already seeds from the expanded file
and top-3 industries; that combination is **A2**, below.

| | n | 5d mean | 10d | 20d | 5d win / PF | 20d MAE med / max |
|---|---:|---:|---:|---:|---|---|
| A0 close | 10 | **+2.33%** | +2.27% | +1.56% | 80% / 10.89 | 3.1% / 9.7% |

Six of the ten trades are `WY`. The rest are `PEP` (2), `UPS` (1), `DOW` (1).
December 2025 and March 2026 produced **zero** A0 triggers. A0’s `watch` column
is always zero because `ism_simple` is binary: selected or not. It has no
WATCH state.

A0 looks clean because the book is tiny and concentrated. It is the baseline
v2 must beat, not a reason to freeze the old twelve names.

## Expanded-universe baseline

**A1_EXPANDED_ONLY** keeps the same `ism_simple` gate and maps **every**
contracting industry through the September 2026 file.

| | n | 5d mean | 10d | 20d | 5d win / PF | 20d MAE med / max |
|---|---:|---:|---:|---:|---|---|
| A0 sparse | 10 | +2.33% | +2.27% | +1.56% | 80% / 10.89 | 3.1% / 9.7% |
| A1 expanded | 47 | **−0.59%** | −0.35% | −0.34% | 59% / 0.75 | 6.6% / 28.8% |

December 2025 mapped 45 names versus 7 under A0. Five-day mean fell 2.92
points; 20-day MAE median rose 3.5 points. Expanding the universe without
changing the gate **increased coverage and destroyed the apparent edge**.

That is the point of keeping A0 and A1 separate. A1 is not “production plus
more names.” It is a different, worse book under the same scorer.

## Incremental factor attribution

Each row adds one idea. A6 is the live `shorts_v2` default
(`deterioration_mode=any`), not a stricter gate on top of A5.

| Variant | Rule | n | 5d | 10d | 20d | 5d PF | 20d MAE med / max |
|---|---|---:|---:|---:|---:|---:|---|
| A0 | Sparse 12 names + `ism_simple` | 10 | +2.33% | +2.27% | +1.56% | 10.89 | 3.1% / 9.7% |
| A1 | Expanded mapping, all contracting, `ism_simple` | 47 | −0.59% | −0.35% | −0.34% | 0.75 | 6.6% / 28.8% |
| A2 | Expanded + top-3 / series, `ism_simple` | 35 | −0.09% | +0.21% | −0.27% | 0.95 | 6.7% / 28.8% |
| A3 | A2 + relative vs sector and SPY | 32 | +0.68% | +0.43% | +0.01% | 1.60 | 6.6% / 39.6% |
| A4 | A3 + cash-flow quality required | 27 | +0.76% | +0.48% | +0.44% | 1.64 | 6.5% / 39.6% |
| A5 | A4 + structured bearish catalyst | 0 | — | — | — | — | — |
| A6 | Live v2 default: any observed deterioration + relative | 40 | +0.86% | +0.67% | +0.13% | 1.78 | 5.6% / 39.6% |

### Does top-3 help?

A1 → A2: n 47 → 35. Five-day mean −0.59% → −0.09%. Still negative. Top-3 is a
**universe bound**, not an edge. It is still the right live discovery rule so
ISM decides where to look. August 2026 Manufacturing had two contracting
industries; v2 uses two rather than forcing three.

### Does relative weakness help?

A2 → A3: five-day mean −0.09% → **+0.68%**, profit factor 0.95 → 1.60. This is
the first increment that is not just “fewer names.” Twenty-day mean is flat
(+0.01%) and max MAE is **worse** (39.6%, `PVH` apparel). Versus A0, A3 is
worse on every horizon and on MAE.

Relative weakness is useful **versus the expanded current gate**. It does not
recover the sparse production book.

### Does cash-flow quality help?

A4 is strictly **A3 + deteriorating cash flow**: `company_fundamentals` must
be True **and** `cash_flow_quality.state` must be `DETERIORATING`. Fundamentals
UNKNOWN or cash-flow UNKNOWN stay UNKNOWN. Fundamentals False or cash-flow not
deteriorating is False. Cash-flow-only names can still pass A6 (`any`); they
cannot pass A4.

Dropped from A3: `ADM` (flat), `DD` (unknown cash flow), `DHI` / `PHM`
(improving). A4 has no extras versus A3. n 32 → 27. Twenty-day mean +0.01% →
+0.44%. Sample numbers did **not** change versus the previous A4 run, because
this window had no fundamentals-UNKNOWN + cash-flow-DETERIORATING triggers.
The semantics are now a clean increment. Still below A0, still carrying the
`PVH` 39.6% MAE.

### Does the live v2 default help?

A6 accepts any observed deterioration (reported fundamentals **or** cash-flow
**or** same-period revisions). Revisions were unavailable, so A6 mainly adds
names whose cash-flow flag is deteriorating while reported EPS growth is not
bearish: `ACN`, `UNP`, `AVY`, `SPG`, `AMT`, `WMT`, `LRN`. Mix of +12.9%
(`ACN`) and −8.9% (`AMT`). n 40, five-day +0.86%, twenty-day +0.13%. Same
shape as the old Variant B, and still not better than A0.

## Catalyst correction

The previous report’s Variant D (n = 32) treated a recent 8-K or S-1 as a
catalyst. That was wrong.

An 8-K is bearish **only** when the item itself is a structured downside
event:

| Item | Type | Direction |
|---|---|---|
| 2.02 | `EARNINGS_EVENT` | UNKNOWN unless EPS actual &lt; estimate |
| 2.05 | `EXIT_OR_DISPOSAL_COST` | UNKNOWN |
| 2.06 | `MATERIAL_IMPAIRMENT` | BEARISH |
| 4.01 | `AUDITOR_CHANGE` | UNKNOWN |
| 4.02 | `NON_RELIANCE` | BEARISH |
| 5.02 | `MANAGEMENT_CHANGE` | UNKNOWN |
| 8.01 | `OTHER_EVENT` | UNKNOWN |
| S-1 / S-3 | `S1` / `S3` | UNKNOWN |

A5 requires `direction=BEARISH`. Result: **zero trades**. None of the A3/A4
names had a 2.06, 4.02, or earnings-miss in the 45-day PIT window. Earnings
surprises were not reconstructed (no FMP/Massive key).

Catalysts stay explanation, not a gate. Requiring one on this sample is a
silent no-trade rule.

## Entry

Close-of-signal versus next-session open. No artificial intraday fill.

| Book | Entry | n | 5d mean | 20d mean | 20d MAE med | 20d MFE med |
|---|---|---:|---:|---:|---:|---:|
| A0 | close | 10 | +2.33% | +1.56% | 3.12% | 7.03% |
| A0 | next open | 10 | +2.45% | +1.67% | 3.56% | 6.34% |
| A3 | close | 32 | +0.68% | +0.01% | 6.61% | 6.11% |
| A3 | next open | 32 | +0.98% | +0.36% | 6.31% | 7.12% |
| A6 | close | 40 | +0.86% | +0.13% | 5.56% | 6.81% |
| A6 | next open | 40 | +1.10% | +0.40% | 5.93% | 7.14% |

Next-open does **not** degrade the edge. On A3 it improves five-day mean by
30 bp and raises MFE. Zero names were skipped for a missing open. Research
P&amp;L may use next-session open; do not invent a same-bar fill.

## Tokenized execution

Present-tense snapshot at 2026-09-16:

| Provider | Status | Coverage |
|---|---|---|
| xstocks.public.assets | HEALTHY | 827 |
| kraken.futures.xstocks_perps | HEALTHY | 16 |
| ondo.perps.contracts | HEALTHY | 81 |
| ondo.current_registry | PARTIAL | reviewed mints; not historical |

August 2026 research names: `ADM`, `ADP`, `BG`, `CTAS`, `CTVA`, `DD`, `DHI`,
`DOW`, `LEN`, `LPX`, `LYB`, `PAYX`, `PHM`, `UFPI`, `WY`.

`EXECUTION_ELIGIBLE` among those names: **none**. Tokenized spot does not
count. Historical execution overlay is not run. The overlay is useful
infrastructure for the caller; it is not a historical short book.

## Edge assessment

| Assessment | Comparison | Result |
|---|---|---|
| `core_edge_assessment` | A3 vs A0 | `EDGE_NOT_VALIDATED` |
| `live_v2_edge_assessment` | A6 vs A0 | `EDGE_NOT_VALIDATED` |
| `edge_assessment` | follows live A6 | `EDGE_NOT_VALIDATED` |
| `infrastructure_assessment` | architecture, not P&amp;L | `useful` |

A3 is the core research increment (top-3 + fundamentals + relative). A6 is
what `--strategy shorts_v2` actually runs (`deterioration_mode=any`). Live
default remains `ism_simple`.

## Month-by-month (A3 and A6)

| Month | Mfg top | Svc top | Mapped | A3 WATCH / TRIG | A6 WATCH / TRIG |
|---|---|---|---:|---|---|
| 2025-12 | apparel; wood; textile | management support; professional; agriculture | 14 | 4 / 3 | 5 / 4 |
| 2026-01 | textile; wood; nonmetallic | other services (unmapped); transportation; management | 12 | 4 / 3 | 5 / 3 |
| 2026-02 | apparel; furniture; petroleum | retail; arts; transportation | 14 | 6 / 6 | 8 / 7 |
| 2026-03 | plastics; furniture; food | retail; agriculture; public admin (unmapped) | 13 | 6 / 3 | 7 / 4 |
| 2026-04 | wood; petroleum; food | agriculture; real estate; retail | 18 | 6 / 3 | 9 / 6 |
| 2026-05 | wood | real estate | 6 | 2 / 1 | 3 / 2 |
| 2026-06 | paper; furniture; wood | agriculture; educational; management | 15 | 4 / 2 | 6 / 3 |
| 2026-07 | chemical | agriculture; other services (unmapped); health care | 9 | 6 / 4 | 6 / 4 |
| 2026-08 | wood; chemical | agriculture; construction; management | 15 | 7 / 7 | 8 / 7 |

Unmapped buckets stay unmapped: `other services`, `public administration`.

## Industries (A6, 20-day short mean)

Useful in this sample: professional services, management support, plastics,
retail, transportation, wood.

Harmful: apparel (`PVH` −38.8% in February), agriculture, arts, real estate,
educational services.

Those means are **one-to-six observations**. Attribution, not a sector model.
`PVH` is why A3/A6 max MAE is 39.6% while A0 stayed under 10%.

Theme/industry tables are **non-additive**: one ticker, one trade, one ISM
month in P&amp;L; every contributing theme can show that same 20-day return.
This nine-month TRIGGERED sample had **zero** multi-theme names, so bucket n
still matches the 20-day-complete trade count.

## Factor attribution example

`PVH`, ISM apparel rank 1, 2025-12 report, first A3 trigger 2026-01-07 close:

- relative vs sector −14.3% band in the first report; February trigger is the
  painful one (−38.8% 20-day short, 39.6% MAE)
- EPS revision UNKNOWN (no vintage)
- cash-flow quality deteriorating
- no structured bearish catalyst after the 8-K correction
- R/R 0.18 on the February trigger (no 1.5 filter)

`WY` is the A0 backbone: six triggers, mixed 20-day outcomes (+10.1%, −3.0%,
−5.3%, +0.3%, −7.8%, August incomplete). A concentrated name that happened to
print a positive five-day mean is not a strategy.

## What improved (infrastructure)

- Incremental variants exist. A0 and A1 can no longer be confused.
- Relative weakness is the only added factor that moved five-day mean from
  negative to positive versus the expanded current gate.
- 8-K item semantics are no longer “any filing is bearish.”
- Downside targets are swing lows in the eligible window, not the
  full-history low. After that fix, R/R ≥ 1.5 has **n = 1** (`FDX`) and
  R/R ≥ 2.0 has **n = 0**. The old E-table was a target artifact.
- Tokenized providers return HEALTHY coverage instead of an empty overlay.
- Next-open P&amp;L is measured. It does not need a fantasy fill.
- Live `--strategy shorts_v2` now acquires v2 snapshots and persists estimate
  snapshots for a future vintage.

## What did not improve / should not be implemented from this sample

- **Do not replace live `ism_simple` with v2.** A3 and A6 lose to A0 on
  20-day mean and on MAE. A2 (current live universe + current gate) is still
  slightly negative.
- **Do not treat A1’s coverage as a win.** n = 47 with PF 0.75 is a worse book.
- **Do not require a bearish catalyst.** A5 is zero trades.
- **Do not require a failed retest.** Prior sample: n = 20, 20-day mean
  **−1.24%**. Keep it optional.
- **Do not hardcode R/R ≥ 1.5 or 2.0.** After the target fix there is almost
  no sample. Leave R/R as context.
- **Do not backfill estimate revisions** from today’s FMP consensus.
- **Do not pretend the September 2026 mapping is a PIT vintage.** Strict PIT
  is n = 0.
- **Do not backfill tokenized shorts** from today’s Kraken/Ondo lists.

## Data limitations

- Yahoo session-close availability is an approximation.
- Next-session open uses the following bar’s open; overnight gap is included,
  the signal-bar close-to-open gap is not when entry is close.
- SEC User-Agent policy required a contact-style header; facts are public
  10-K XBRL, not a paid fundamentals vintage.
- FMP/Massive keys were absent. Earnings-miss catalysts and estimate
  revisions could not be reconstructed.
- No borrow fees, days-to-cover, funding as P&amp;L, or depth.
- Mapping knowledge timestamp is September 2026.
- Sample is nine months in a generally expanding 2026 manufacturing cycle
  after the December 2025 contraction. Results are regime-specific.
- A0’s profit factor 10.89 is one-sided because the ten-trade book had almost
  no five-day losers. Do not optimize for that number.

Machine-readable summary: `docs/analysis/data/shorts_v2_backtest.json`.
