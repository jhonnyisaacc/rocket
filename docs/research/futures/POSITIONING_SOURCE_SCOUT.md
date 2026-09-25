# Positioning-data source scout after FUT-004

Status: `2022_PANEL_COVERAGE_AUDITED`, 2026-09-25. This is a return-free source investigation, not FUT-005 or an open-interest signal. No open-interest change, price-conditioned factor, forecast-times-return, portfolio outcome, or new parameter was selected.

The [Binance USD-M open-interest-statistics API](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics) currently documents only the latest **one month** of history. It therefore does not provide Rocket's 2022–2025 historical cross-section by itself. [Bybit's open-interest API](https://bybit-exchange.github.io/docs/v5/market/open-interest) documents daily intervals, a 200-row page limit, and queries back toward each symbol's launch. Its `openInterest` is the **sum of both sides**; for linear USDT contracts the unit is the base asset. It is a participation measure, not a long-minus-short positioning signal. Historical completeness and point-in-time publication delay need direct audit.

`research/futures/bybit_oi_probe.py` requested five fixed one-month windows without computing returns. The ignored raw responses are retained with individual hashes in the local report, SHA-256 `2e1a1a1344075701efa277bfc29735e4c570cae9f0b2e23921395c22aeb0dba4`.

| Symbol | UTC month | Returned daily rows | First–last listed day |
| --- | --- | ---: | --- |
| BTCUSDT | 2022-01 | 31 | Jan 1–31 |
| ETHUSDT | 2022-01 | 31 | Jan 1–31 |
| FTTUSDT | 2022-11 | 30 | Nov 1–30 |
| BTCUSDT | 2024-01 | 31 | Jan 1–31 |
| BTCUSDT | 2025-01 | 31 | Jan 1–31 |

The FTT response reports zero OI from November 14 onward after trading ceased. Those rows cannot be treated as ongoing tradable-contract observations. A separate checksum-equivalent raw-response hash `f32f29e1f63501ec540342ff70c6827a5bb9baa08a7fbcc5cd55ad1f3218a73d` covers a 24-row BTCUSDT hourly OI query on January 1, 2022. Its 00:00 UTC observation exactly matches the daily observation timestamped 00:00 UTC that day. This is one timestamp-semantics check, not proof of when every daily value became available to a trading bot; a conservative later decision lag would be needed.

The five initial windows established an older Bybit OI source, including a now-closed symbol, but did not establish a broad historical universe, pagination integrity, absence of revisions, correct post-delisting treatment, or any predictive mechanism. The full 2022 panel audit below addresses pagination and observed-price coverage while leaving point-in-time revisions, publication latency, later years and directional use unresolved. A distinct positioning hypothesis must explain why a **change in aggregate OI**, in combination with independently defined market information if needed, forecasts directional returns; an OI level alone gives no side. [Research on exchange OI measurement](https://arxiv.org/abs/2310.14973) also motivates cross-checking reported values before interpreting them. Do not invert FUT-004 or fit an OI threshold to inspected 2022–2023 factor returns.

## Full 2022 candidate-panel audit

The resumable [OI coverage auditor](../../../research/futures/bybit_oi_coverage.py)
queried **all 190** pre-2023 USDT perpetual candidates from the existing
[Bybit price/funding inventory](INDEPENDENT_VENUE_DATA.md), including
64 currently closed names. The candidate inventory is based on today's
catalog and is not proof that every historical delisting is preserved.
For each symbol it paginated backward through the entire 2022 daily OI
window, saved and hashed **361** raw API pages (5,709,852 bytes), checked
daily timestamp uniqueness/alignment, nonnegative values, and agreement
between the double- and single-side OI fields allowing one basis point
for contract-step rounding. All 190 requests completed without a source
page failure. The local report SHA-256 is
`8cec7dfd4f710994321227b30f4c717e12830dcd19e1f57b00f8f0a4cac27ce9`;
its candidate inventory SHA-256 and individual page hashes are embedded
in the report. A fresh Jan 1, 2022 BTC response matched the previously
saved sample's `openInterest` and `singleOpenInterest` values exactly.

| 2022 source observation | Count |
| --- | ---: |
| Daily OI rows returned | 59,174 |
| Days with observed Bybit trading bars in the candidate panel | 58,414 |
| Observed price days missing an OI row | 340 |
| Observed price days with a zero OI row | 0 |
| Symbols with positive OI on every observed 2022 price day | 100 of 190 |
| Positive OI rows outside observed price days | 151, all GSTUSDT |

For 85 names, the only absent active OI observation is the first
observed trading day. Four closed or renamed names have longer gaps:
LUNAUSDT 115 days, KEEPUSDT 49, BTTUSDT 45 and ANCUSDT 42. Their OI
responses begin on April 26, 2022, after some or all of their observed
trading history. GSTUSDT has four missing initial active days and
**151 positive OI rows after its July 21 last price bar**; the stale
post-closure value is 22 base units on sampled later dates. FTTUSDT OI
is positive on its November 13 last bar and zero from November 14 in
the sampled response. In total, 949 returned OI rows are zero, many
after contract closure. Neither positive nor zero OI alone grants
tradability; require same-day observed bars and prior funding, as in
the existing eligibility preflight.

[Bybit's API](https://bybit-exchange.github.io/docs/v5/market/open-interest)
defines `openInterest` as both sides summed and linear-contract units as
base asset. [Bybit's June 2026 methodology announcement](https://announcements.bybit.com/en/article/--blta89d9c88819bfebe/)
says the platform display changed to single-side OI and the API added
`singleOpenInterest`; it does not establish point-in-time publication
latency or prove older records were never revised. The 2022 panel is a
feasible *source*, with explicit missing and delisting masks. A causal
directional mechanism, a conservative observation lag, subsequent-year
coverage and an uninspected evaluation chronology are still required
before a frozen OI strategy trial. OI is aggregate participation across
longs and shorts, so no sign follows from its level alone.
