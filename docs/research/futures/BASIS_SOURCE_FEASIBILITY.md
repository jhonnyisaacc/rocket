# Spot/perpetual basis source feasibility

Status: `DIRECTORY_AND_FOUR_FILE_PROBE`, 2026-09-24. This is a source audit for a possible new directional mechanism, **not** FUT-004 or an outcome test. No spot price value, basis, forecast-times-return, or new portfolio score was inspected.

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

Before a basis experiment is frozen: verify monthly ZIPs against published checksums; parse both timestamp units; align spot and perpetual completed candles without looking ahead; audit actual day-by-day overlap, zero-volume/abnormal bars, contract multipliers and renamed assets; define funding and closure handling; reserve an independent chronology and a single sign/horizon/portfolio rule with an explicit gross-information falsifier. The 2026 Binance final holdout remains sealed. The prior 2022–2025 futures outcomes have already been examined for other signals, so a test on them must be labelled another trial, not a pristine holdout. Do not claim a tradable basis edge from this inventory.
