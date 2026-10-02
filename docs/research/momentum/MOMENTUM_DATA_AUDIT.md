# Momentum data audit

Scope: updated main 09d7150; no unmerged strategy stack imported. Plan freeze
3272afc. Historical source: BTCUSDT spot 1h, UTC 2019-01-01 through
2025-12-31. SOURCE_MANIFEST.json records every ZIP hash, URL and actual ingestion.

## Market clocks and integrity

84 official monthly ZIPs are verified against published SHA-256 sidecars.
61,309 vendor rows are present; 61,300 survive the frozen source rule. Of
61,368 expected hours, 59 have no vendor row and nine present rows are
quarantined, yielding 68 unusable slots. All nine were already recorded in
the original manifest. One zero-volume row opens 2019-06-07 21:00 UTC
(1559941200000), with close_time 1559941993524 about 13 minutes later.
An anomalous timestamp alone is not proof of invalid prices or causality;
the frozen contract explicitly requires ideal end-minus-one-unit equality.
Gaps are retained in the source manifest, never filled. Full 4h aggregation
requires all four aligned hourly bars. A 30d feature window touching any gap
is UNKNOWN; a label window touching a gap is UNKNOWN.

[Binance's public archive documentation](https://github.com/binance/binance-public-data/blob/master/README.md)
defines the columns, 2025 spot microseconds, checksum sidecars and corrections
to historical files. Source integrity is not original historical availability.
The archive was received in October 2026: bars assume market availability at
end+5m for reconstruction. Current corrected vintage is explicit. We do not
claim authentic historical source receipts. Prospective collection timestamps
actual receipt, preserves raw bytes, and rejects late inputs.

4h decisions use full 1h data; timestamp semantics are tested. First future
hour starts one hour after cutoff, conservatively excluding the partially
observable decision hour. Reference close is descriptive, not an executable
entry. Extra 4h delay and 20/40/80bp hurdles are sanity checks, not leveraged
PnL. US assets do not update on crypto weekends; no US/macro series enters.

## Existing FRED and other PIT risks

Main rocket/providers/fred.py retrieves OpenBB or normal FRED CSV with
observation dates, retrieval timestamps and no realtime_start/realtime_end.
These are current reported history. It does not establish original release
availability or revision vintages. Main's PointInTime is useful eligibility
infrastructure but cannot repair invented or absent availability metadata.

PR #40 rocket/market_check/fetch.py also downloads normal FRED CSV, including
DCOILWTICO/DCOILBRENTEU, VIXCLS, HY/IG spreads and DTWEXBGS; its date/lag panel
limits future observation dates but carries no vintage identity. Historical
values can reflect today's revisions. DCOIL is spot oil, not futures. Fixed
lags do not recover publication calendars, especially weekly H.10 dollar data.
[The FRED realtime documentation](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)
distinguishes current history from as-known history explicitly. Future macro
features (balance sheet WALCL, Treasury account WDTGAL, reverse repos,
EFFR, dollar/credit/economic releases) require series-specific revision audit,
release calendar and ALFRED/equivalent vintages where revised. Even relatively
stable market series need publication/receipt proof; none is declared PIT by
virtue of a CSV. We do not rebuild ALFRED in this iteration.

PR #38 FUT-009 used a delayed Yahoo DXY proxy, not a vintage-clean exact paper
replication; known vendor revisions remain unresolved. Its negative result
is preserved. COT must use publication, not Tuesday position date. PR #38's
release-lagged FUT-005 still failed. PR #26 has today's exposure mappings,
zero strict-PIT historical mappings, unknown estimate vintages/borrow, and
filing-date approximations. These are explicitly inherited limitations.

PR #46 uses daily spot/funding/DVOL, live option calibration and approximated
historical options prices; neither that calibration nor daily DVOL is a
verified 4h implied-magnitude baseline. No B4 is admitted.

## Feature readiness (reserved, not scored)

| Feature | Raw source, clocks, transformation | Mechanism/prior evidence | Missing policy |
| --- | --- | --- | --- |
| Signed 24h return | Closed spot 1h→4h, end+5m assumed; signed log return / sigma sqrt(6); 2019–2025 | Persistence conditional on a breakout; inherits failed standalone trend/breakout, no profit assumption | Incomplete window UNKNOWN |
| RV ratio | Same; SD(last 6 returns)/SD(last 180) | Speed of volatility expansion; unsigned magnitude, not direction | Zero/gapped RV UNKNOWN |
| Relative volume | Same; mean last 6 / mean preceding 174 bar volumes | Participation; not an additional candle confirmation | Missing/zero denominator UNKNOWN |
| Funding 24h | Realized funding history; settlement event and independently established available_at needed | Crowding vs continuation; FUT-007 failed tails, carry is different payoff; expected sign unresolved | Receipt/coverage UNKNOWN; no current backfill |
| OI log change 24h | Historical venue OI with publication/receipt, vintage and instrument identity | Participation has no signed mechanism; PR #38 unsigned OI frontier persists | Daily archive files verified September 2020–December 2025; original publication/receipts unverified, operationally UNKNOWN |
| Spot/perp quote-volume ratio | Matched two-venue 24h bars, common cutoff and receipt | Spot participation vs leveraged demand; conditional role untested; basis failure preserved | Perp history acquired and verified; feature joins not scored or admitted, UNKNOWN |

Only price features exist operationally. Tier B and historical IV are not
silently proxied. Source feasibility alone never establishes alpha.

## Contamination

2019–2025 has been inspected in prior Rocket research and is development data.
PR #40 and #46 already exposed 2026 prices/outcomes. We exclude 2026 from
historical census by pre-registration; it is not a pristine holdout. Prospective
records created now, without future labels, are the eventual validation basis.

Provider metadata improvement: normal FRED CSV/OpenBB payloads and the
FredMacroSeries adapter now explicitly expose CURRENT_REPORTED_HISTORY,
historical_pit=false, vintage_id=null and available_at=null. The observation
date is never relabeled as publication. Mock-source tests pin this distinction;
operational acquisition behavior and record values are preserved.

## Reconciliation and source readiness, 2026-10-02

[Replication report](REPLICATION_REPORT.md) distinguishes nine vendor-clock
anomalies, 59 absent hours, 35 incomplete 4h groups and 3,219 scheduled
gap-induced UNKNOWN decisions. It corrects the old prose's UTC conversion,
without modifying any source bytes or exclusions. Close=end-minus-one-unit
is a vendor convention and an explicit frozen source rule, not a universal
requirement of causal correctness. [Source v2 proposal](SOURCE_CONTRACT_V2_PROPOSAL.md)
is separate, not activated, and cannot replace MOM-000 or change MOM-002's
inherited population after observing outcomes.

[Tier B source audit](TIER_B_SOURCE_AUDIT.md) and its manifest independently
verify all 72 requested monthly perp/funding ZIPs, all 1,948 daily metrics
file names, and monthly premiumIndexKlines availability. Daily metrics contain
intraday OI snapshots and can contain exact duplicates; funding timestamps
can lie milliseconds after nominal boundaries. Actual historical receipts
and first-release vintages remain absent. These are readiness findings, not
PIT certification or predictive skill. No Tier B feature is scored.

[CFTC lineage audit](CFTC_LINEAGE_AUDIT.md) confirms FUT-005 used its own
annual-ZIP path with conservative release timing, not the current live
provider. All 313 availability dates and six ZIP hashes agree with the frozen
auditor. No timing replay is needed and COT remains closed. Future live
provider records now distinguish positions date, actual post-fetch receipt,
unknown original publication, source-byte identity and historical_pit=false.
FRED's five-way distinction remains: current reported value, observation date,
unknown historical availability, unknown vintage/revision identity and false
historical PIT capability. No global ALFRED migration is introduced.
