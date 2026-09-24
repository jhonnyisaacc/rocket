# Daily dollar-index forecast: economic and source screen

Status: `PROXY_ROWS_ACQUIRED_CLOCK_AND_COVERAGE_UNRESOLVED`, 2026-09-24. No dollar-conditioned
Rocket return, fitted coefficient, or new strategy rule has been scored.
This is a possible **daily BTC directional** mechanism after FUT-008, not a
continuation or threshold change of any failed trial.

## Prior and economic hurdle

[Arain and Snudden (2026)](https://onlinelibrary.wiley.com/doi/full/10.1002/for.70077)
fit expanding daily bivariate VAR forecasts for spot BTC returns using one
macro predictor at a time. Their USD-index version reports 146% summed
long-short gross return over their October 2021–February 2024 evaluation
period, compared with 15.79% BTC buy-and-hold; a forecast-magnitude
condition reports 217.65%. This is a materially larger published gross
prior than sub-basis-point microstructure forecasts, but it is selected
from many predictors and strategy variants and is **spot** evidence on a
weekday calendar. Neither statistic proves perpetual P&L or later-period
stability. Do not select the paper's magnitude threshold by its result.

The published fee table cannot be adopted as cost evidence. It states a
**0.2% fee per active trade**, 305 USD-index long-short trade days, and
gross/net returns of 146%/140%. Since the paper defines cumulative return
as a sum of daily returns, 305 × 0.2% = **61 percentage points**, while
the reported reduction is **6 points**. The below-threshold column has
146 trade days and 203%/200% gross/net, likewise 29.2 versus 3 points.
The numbers are approximately consistent with **0.02%** per counted day;
this is an arithmetic inference, not a corrected paper result. A Rocket
test must charge actual side-based target changes plus spread, impact and
funding, and must report daily gross before any net claim. The paper also
describes 325 trades in prose beside a table showing 305 trade days; the
execution unit needs independent definition.

## Point-in-time source

The paper aligns predictor closes at 14:00–19:00 Eastern with a 19:00
Eastern BTC close and sources most series from Investing.com. It does not
publish row-level data; its data-availability statement offers data from
the author upon request. The named “US Dollar Index” is not specified
with an exchange symbol or immutable vintage in the accessible method.

[ICE identifies DXY/USDX](https://developer.ice.com/fixed-income-data-services/catalog/ice-data-indices-currency-indices)
as its six-currency fixed-weight index and lists historical intraday and
daily delivery through ICE data products. ICE's index and USDX futures are
different objects; a futures settlement is not a silent substitute for a
spot-index close. The [Federal Reserve H.10 broad dollar index](https://www.federalreserve.gov/Releases/H10/)
is a different currency basket and its daily observations are ordinarily
**published the following Monday for the previous business week**.
Historical observation date therefore is not a same-day availability time.
Its daily [DTWEXBGS series](https://fred.stlouisfed.org/series/DTWEXBGS)
can support a separate weekly-publication-lag hypothesis, not a faithful
paper-series replication.

[Yahoo's `DX-Y.NYB` historical page](https://finance.yahoo.com/quote/DX-Y.NYB/history/)
labels its series “US Dollar Index” and “ICE Futures”; [Yahoo's market
coverage page](https://help.yahoo.com/kb/SLN2310.html) lists ICE Data
Services for NYB. A read-only chart-API acquisition saved the raw
2017-01-01 through 2025-12-31 request as ignored local
`.rocket/futures_data/macro/dxy_yahoo_2017_2025_raw.json` (250,543 bytes;
SHA-256 `330480474ef50919a17998ffa2210471fde23d17dd2165319985299393754d88`).
Its metadata says `instrumentType=INDEX`, `exchangeName=NYB`,
`fullExchangeName=ICE Futures`, `exchangeTimezoneName=America/New_York` and
`dataGranularity=1d`. This is a plausible secondary delivery route for an
index-family-matched archive, not proof of the paper's exact series or
close convention.

The JSON contains **2,736 timestamped rows**, of which **2,264 have a
non-null close**: 251, 251, 252, 253, 252, 251, 250, 252 and 252 by year
2017–2025. There are no duplicate New York session dates, nonpositive
valid closes, or non-null weekend closes. Of 472 null closes, 469 are
Sunday placeholders and three are dated 2023-11-23, 2025-06-19 and
2025-07-04. Twenty otherwise valid rows use a **09:30 New York timestamp**
on shortened-market dates; most others use midnight New York. These are
bar labels, **not** reliable release or close timestamps. A causal trial
must assign a conservatively delayed availability time from external
market-calendar evidence and refuse stale or missing observations. Exact
vendor revisions and index-versus-futures alignment are still open.

The proxy follows a narrower holiday calendar than [ICE's April 2021
DXY methodology notice](https://www.ice.com/publicdocs/equity_indices/notices/DXY_ICE_FX_Indices_Methodology_Updates_20210311.pdf),
which says the index is calculated on weekdays except Christmas and New
Year's Day or observed equivalents. For example, Yahoo has no valid
2024-01-15, 2024-02-19, 2024-05-27 or 2024-09-02 close; those are among
**10 missing weekdays in 2024**, of which only two are the stated ICE
index holidays. The same audit found 10 missing weekdays in 2023 and nine
in 2025. Yahoo's daily proxy therefore fails **full ICE-calendar
coverage**. Missing dates must not be filled forward and described as
fresh macro information. A separate source or an explicitly sparse,
delayed hypothesis is required before a frozen trial.

## Decision before another numbered trial

This mechanism merits a source gate because of its daily turnover and
published gross scale. Reconcile the acquired proxy against the paper's
index identity and documented ICE close, time zone, publication latency,
missing holidays, revisions and 2019/2021 methodology changes. Confirm
that the value was available *before* each prospective BTC perpetual
decision and preserve an as-of manifest. If an exact or defensibly delayed
series cannot be established, pursue another mechanism rather than using
H.10 observation dates or Yahoo session labels as publication dates.

Then freeze one simple causal forecast and a chronological cheap gross
falsifier under a new experiment ID **before** inspecting its conditioned
returns. A paper-model replication would need the complete VAR, lag
selection, estimation window, target clock, weekend rule and source
identity. A deliberately simpler dollar-change rule would be a distinct
trial, not evidence that the paper's model replicated. Score controls,
actual turnover/funding and intended-venue cost stress; 2026 remains the
final untouched holdout. No live decision follows from this scout.
