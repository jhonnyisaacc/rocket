# Daily dollar-index forecast: economic and source screen

Status: `SPARSE_DELAYED_PROXY_SOURCE_READY`, 2026-09-24. No dollar-conditioned
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

A deterministic [source-clock normalizer](../../../research/futures/dxy_asof.py)
verified the raw SHA and preserved all 2,264 valid session dates, then
assigned each close an **earliest allowed** timestamp of 03:00 UTC on the
following calendar date. This is after 22:00 or 23:00 local New York time
on the source session date, later than the [ICE notice's pre-2021 19:15
Eastern publication endpoint](https://www.ice.com/publicdocs/equity_indices/notices/DXY_ICE_FX_Indices_Methodology_Updates_20210311.pdf).
It does not assert the Yahoo bar timestamp is a release time or fill the
holiday gaps. The ignored local `dxy_yahoo_2017_2025_asof.json` has
SHA-256 `8c8427fa1ed62c38466fed10b4785d1754f8f25227100c8a7e053047a1143e40`.
This makes the proxy usable only for a separately labeled **sparse and
delayed** hypothesis; vintage revisions and exact paper-series identity
remain unverified.

For that distinct hypothesis, a [BTC hourly source auditor](../../../research/futures/btc_macro_hourly_source.py)
acquired **48 official Binance BTCUSDT USD-M monthly 1h ZIPs** for
2022–2025 and matched each to its published `.CHECKSUM`. All 35,064
hourly rows are consecutive, with 8,760/8,760/8,784/8,760 hours by year,
valid OHLC and exact hour-end clocks. The already checksum-repaired
BTC funding database has 1,095/1,095/1,098/1,095 consecutive eight-hour
slots in those years. The ignored local hourly `source_audit.json` has
SHA-256 `bcbcfdb4d6b5af752abf65edbbcff5258c9cdfacace0b948d5dcc7add7425af1`;
it records every ZIP source hash. The funding database SHA-256 is
`e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b`.
No future BTC return was paired with a dollar observation in these audits.

## Decision before another numbered trial

The source gate admits a **sparse delayed proxy trial**, with no signal on
missing Yahoo sessions. It does not admit a replication claim. A closer
paper replication would still need reconciliation of exact index identity,
vendor vintages and missing holiday values. H.10 observation dates and
Yahoo session-label timestamps remain inadmissible as publication times.

Then freeze one simple causal forecast and a chronological cheap gross
falsifier under a new experiment ID **before** inspecting its conditioned
returns. A paper-model replication would need the complete VAR, lag
selection, estimation window, target clock, weekend rule and source
identity. A deliberately simpler dollar-change rule would be a distinct
trial, not evidence that the paper's model replicated. Score controls,
actual turnover/funding and intended-venue cost stress; 2026 remains the
final untouched holdout. No live decision follows from this scout.
