# CME BTC COT source and publication audit

Status: `SOURCE_AUDITED_UNSCORED`, 2026-09-24. This audit does not inspect
COT-conditioned BTC returns or choose a signal threshold.

The [CFTC historical compressed archive](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm)
provides annual legacy futures-only COT ZIP files. The fixed CME BTC contract
code is `133741`; micro BTC `133742` and Nano BTC `133LM1` are distinct
markets and are not mixed into this series. Six downloaded official ZIPs,
2020–2025, contain 313 weekly BTC records (52, 52, 52, 52, 53, 52). The
[auditor](../../../research/futures/cftc_cot_source_audit.py) verifies the
contract identity, annual date, noncommercial long/short availability,
nonnegative counts, and equality of reported plus nonreportable positions to
total open interest on both sides. Its local source manifest SHA-256 is
`a51fc0dc3461ad67ddd85b9e531b60f783546dc91a28c9f5e635bb7a8d6a830a`,
which includes every ZIP hash. The first as-of date is 2020-01-07 and the
last is 2025-12-30. Maximum gap between as-of dates is eight days. The
checksum-repaired Binance BTCUSDT research tape has all 2,192 daily bars
and 6,576 funding records during 2020–2025, with no untradable BTC daily bar;
its database SHA-256 is
`e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b`.

The as-of date is **not** the publication date. The [CFTC description](https://www.cftc.gov/MarketReports/CommitmentsofTraders/AbouttheCOTReports/cot_about.html)
says Tuesday positions normally publish Friday at 3:30 p.m. Eastern.
The auditor conservatively allows an ordinary row only at UTC midnight ten
calendar days after its as-of date. Its 21 exceptional rows use the later of
that lag and the day after the actual exceptional publication. The
[CFTC special-announcement archive](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm)
documents the 2023 ION reporting delays, the 2025 January delay, and an
amended catch-up calendar after the 2025 funding lapse. In particular, a
2025-09-30 report was not published until 2025-11-19; treating its Tuesday
as-of as immediately available would leak nearly seven weeks. The 2025
exception map uses the CFTC's **December 9 amended** schedule, not the
superseded November 18 schedule. Rows that finally publish too late for a
live 21-day maximum signal age will be skipped under the frozen trial.

This is a CME positioning measure, used to inform a Binance perp research
decision and later Hyperliquid venue validation; transfer between those
markets is unproven. Noncommercial positions include reportable speculative
accounts and should not be presented as a direct census of retail traders.
The current annual ZIPs may incorporate later revisions; their first-release
values have not been reconstructed. The conservative date rule establishes
chronological availability, subject to that revision limitation, and does
not itself establish a tradable edge.
