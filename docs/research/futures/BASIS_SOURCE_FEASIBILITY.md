# Spot/perpetual basis source feasibility

Status: `ROW_LEVEL_SOURCE_READY`, 2026-09-24. This is a source audit for a possible new directional mechanism, **not** FUT-004 or an outcome test. No basis forecast-times-return or new portfolio score was inspected. A data-quality check counted extreme same-day spot/perpetual close ratios without using future returns.

One candidate mechanism is that the spot/perpetual price difference measures directional positioning pressure. This is a hypothesis, not an established signal for Rocket. The [empirical cryptocurrency-futures factor study](https://doi.org/10.1002/fut.22425) motivates investigating basis, but its result cannot be transferred directly to a daily perpetual-only directional trade. In particular, perpetual funding, contract type, price alignment, and the sign and duration of any predictive effect require their own frozen test.

[Binance's public-data documentation](https://github.com/binance/binance-public-data/) specifies downloadable spot klines and `.CHECKSUM` files. It also warns that spot timestamps from January 2025 use microseconds, whereas earlier files use milliseconds. `research/futures/spot_source_audit.py` read only monthly-archive directory names and compared them with symbols having observed tradable daily bars in the existing normalized Binance futures database. The local, ignored JSON report has SHA-256 `557a2ab6f81116e01e746cf3672294769e0a06c846aa53ceea1b758eca1f27ce`.

| Year | Observed tradable USDT futures names | Same-name spot archive directories |
| --- | ---: | ---: |
| 2022 | 162 | 153 |
| 2023 | 246 | 228 |
| 2024 | 374 | 327 |
| 2025 | 587 | 408 |

The spot archive listing contains 3,710 symbol directories, 735 ending in `USDT`. These counts establish only that a source worth auditing exists. A directory may lack the needed 1d months, and the archive may retain later listings; equality of ticker text does not prove equality of economic exposure. Neither directory membership nor any current exchange catalog can supply a point-in-time universe.

`research/futures/spot_month_probe.py` then verified published SHA-256 sidecars for BTCUSDT and ETHUSDT January 2024 and January 2025 1d ZIPs. Each contained 31 gap-free UTC daily rows with valid positive OHLC and nonnegative volume. The 2024 timestamps were milliseconds and the 2025 timestamps microseconds, as the source documents. The ignored local report has SHA-256 `adbe44048637779cbe7e613195194b09f80fda1426a63f37916e9ccdb5914efd`; the four raw ZIPs remain under the local `spot_month_probe` directory with their individual hashes in that report. These two names and two months do not establish broad spot coverage.

## Full candidate-source audit

`research/futures/spot_month_inventory.py` listed 1d ZIP keys for 451 same-name candidates with observed futures bars. Its local manifest SHA-256 is `32e26833a9988c6d9ffb2c37ec3f63c71524e04cb0a21149ec8b929445d209ac`. File-level overlap is below; a ZIP key is not proof of a valid bar on every day.

| Year | Observed tradable perpetual symbol-months | Same-name spot ZIP months |
| --- | ---: | ---: |
| 2022 | 1,724 | 1,656 |
| 2023 | 2,333 | 2,186 |
| 2024 | 3,405 | 3,026 |
| 2025 | 5,470 | 4,074 |

`research/futures/spot_download.py` fetched all 13,947 listed monthly ZIPs and verified each published SHA-256 sidecar: zero acquisition failures. Its local run report SHA-256 is `d6aa4d03ce435039b450f112e0432846a137d11d4c86ee324400e1dd89ec2d3a`. `research/futures/spot_normalize.py` accepted 13,946 monthly files and quarantined one checksum-valid malformed month, KLAYUSDT October 2024. That monthly file mixes timestamp units and contains a close time before its open. The local normalization report SHA-256 is `cc71e28d1f5cfeade3c7960c1422a693e4820eb0b8def73fa5ad2c13291e5769`.

The separate daily archive had 30 KLAY October ZIPs. `research/futures/spot_daily_repair.py` verified all 30 checksums, accepted 29 valid daily bars and quarantined October 30, whose daily record also has an impossible interval. October 31 has no listed daily ZIP. Neither day was imputed. The daily repair report SHA-256 is `5c05f222ba9a5d2e304431f2c311677e0a245dd74dba46128235eea18b87da31`. One valid October daily file used microsecond timestamps before the generally documented January 2025 change, so the parser detects units per row and checks actual UTC intervals. The final separate spot SQLite tape has 420,429 rows from 13,946 accepted monthly files plus 29 daily replacements, with 73 explicitly incomplete-day rows and four internal monthly gaps. Incomplete days are ineligible as completed signal bars. Final database SHA-256: `32e9f95a3a4a4773faaab4724d06aa66def137dc56457f063de0308c40f65de8`.

The row-overlap audit (local report SHA-256 `9ace89932bd911eb0d4d68b2df33b513fbb526d9df701f6924bfb3b583e6c6ae`) found a valid prior completed spot and perpetual row on 49,328, 64,987, 90,293 and 121,656 observed tradable perpetual entry days in 2022–2025 respectively. This is **ex-post source coverage**, not a point-in-time trading universe. Four same-day valid close pairs exceeded a 2:1 or fell below a 1:2 perpetual/spot ratio: LUNAUSDT 2022-05-12, COMBOUSDT and LINAUSDT 2025-03-27, and ALPACAUSDT 2025-04-30. They remain flagged data/closure cases; no strategy side or return was inspected and no ratio-based signal threshold was selected.

`research/futures/spot_eligibility.py` separately measured **return-free causal input eligibility** using 30 consecutive completed prior spot and perpetual days, mean prior quote turnover at least USDT 5 million in **each** market, and complete prior funding cadence. It never requests an entry or exit price. The ignored eligibility report SHA-256 is `8415009640658abc93619df0cd6abdc1592e91de1ff3f5e211edd034ab189d71`.

| Entry year | Eligible symbol-days | Distinct names | Days with at least 20 names | Median daily names |
| --- | ---: | ---: | ---: | ---: |
| 2022 | 26,625 | 143 | 334 | 76 |
| 2023 | 31,187 | 210 | 364 | 77 |
| 2024 | 54,835 | 294 | 365 | 138 |
| 2025 | 47,069 | 372 | 364 | 126 |

The 2022 count begins after January warmup; each year stops before an exit would cross into the next year. These counts support a broad source-backed trial, not a claim of tradable returns. Exact same-name pairing deliberately excludes multiplier and index-like futures without an independently verified spot mapping. The eligible list is built each day from prior observations, not from a current catalog or future file presence.

Before a basis outcome test: freeze a single sign/horizon/portfolio rule and gross-information falsifier; define what a held position does at any missing next open, including cessation; preserve the full-source hashes above; and reserve a later independent chronology and execution venue test. The 2026 Binance final holdout remains sealed. Prior 2022–2025 futures outcomes have already been examined for other signals, so a new mechanism tested there is another trial, not a pristine holdout. Do not claim a tradable basis edge from this source audit.
