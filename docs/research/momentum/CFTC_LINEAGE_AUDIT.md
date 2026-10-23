# CFTC availability and FUT-005 lineage

Audited 2026-10-02. `FUT-005` remains `GROSS_GATE_FAILED_2023` and closed to
automatic continuation. This audit does not rerun it, inspect its unscored
conditional 2025 outcomes, add COT to momentum, or authorize a successor.

The current live CFTC provider lacked publication/receipt availability on its
direct records. That is a shared infrastructure defect. **FUT-005 did not use
that provider and did not equate Tuesday positions with Tuesday knowledge.**
Its frozen release rule independently delayed every historical record.
The separate risk of subsequently revised annual COT values remains.

## Evidence identity and exact data path

The audited PR #38 branch revision is
`dedb8e42794f47b70e68c4b7f6cec89fc48f1d6f`. Its
[scorer](https://github.com/jhonnyisaacc/rocket/blob/dedb8e42794f47b70e68c4b7f6cec89fc48f1d6f/research/futures/fut005_cot_score.py)
imports `CODE`, `YEARS`, and `available_date` from
`research.futures.cftc_cot_source_audit`, and funding accounting from
`research.futures.fut001`. Neither this scorer nor that source auditor imports
`rocket.providers.cftc` or its OpenBB adapter.

`load_cot()` reads six cached official annual legacy futures-only ZIPs,
`deacot2020.zip` through `deacot2025.zip`, selects CME BTC code `133741`,
checks every ZIP against the pinned source manifest, and computes positioning
balance and its preceding-as-of change. These are different inputs from the
current HTML report. Historical source paths at audit time:

- `/Users/jhonny/rocket/.rocket/futures_data/cftc_cot/source_audit.json`
- `/Users/jhonny/rocket/.rocket/futures_data/cftc_cot/deacot{2020..2025}.zip`
- `/Users/jhonny/rocket/.rocket/futures_data/fut005_cot_2023_2024.json`

The manifest SHA-256 is
`a51fc0dc3461ad67ddd85b9e531b60f783546dc91a28c9f5e635bb7a8d6a830a`.
All six cached ZIP fingerprints still match it. It contains 313 CME BTC
records, 2020-01-07 through 2025-12-30, with annual counts 52/52/52/52/53/52.
All 313 recorded availability dates equal the frozen auditor's rule. The
existing result file SHA-256 remains
`ae83edc43a499403b326f2f2c0856b5b30002132b4e93ca02ed4755432688c43`;
hashing it neither recalculates returns nor rewrites evidence. The scorer also
pins the Binance research SQLite SHA-256
`e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b`.

The original contract/source freeze was commit
`2538180d5505acf966d67576ac2d1a0e0cf89027`; scoring/result was
`6f7c334e253a76beb0b2b84adea3e5952613a6eb`. Their availability semantics are
unchanged at the audited branch head. A subsequent lint repair only replaced
adjacent `zip(rows, rows[1:])` iteration with `itertools.pairwise`.

## Position date, release date, and conservative eligibility

[CFTC's report description](https://www.cftc.gov/MarketReports/CommitmentsofTraders/AbouttheCOTReports/cot_about.html)
distinguishes Tuesday positions from normal Friday 15:30 Eastern publication.
An as-of date alone cannot establish knowledge time. Exceptions are real:
the [official historical announcements](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm)
document the 2023 ION reporting disruption and delayed catch-up releases.

The frozen auditor permits ordinary rows only at **UTC midnight as-of + ten
calendar days**, which is deliberately later than an ordinary Friday release.
For an explicitly documented exception it takes the later of that date and
UTC midnight following the actual release. `daily_targets()` selects the
latest row with `available <= entry_date`, then enforces a maximum 21-day
as-of age. It checks release dates remain chronological, so the preceding
as-of record used in a change is not a later-unavailable report.

| Positions as-of | CFTC actual exceptional release | Frozen first eligible UTC date |
| --- | --- | --- |
| 2023-01-31 | 2023-02-24 | 2023-02-25 |
| 2023-02-07 | 2023-03-03 | 2023-03-04 |
| 2023-02-14 | 2023-03-08 | 2023-03-09 |
| 2023-02-21 | 2023-03-10 | 2023-03-11 |
| 2023-02-28 | 2023-03-14 | 2023-03-15 |
| 2023-03-07 | 2023-03-16 | 2023-03-17 |
| 2023-03-14 | 2023-03-21 | 2023-03-24 |

The last row remains March 24 because the ordinary ten-day floor is later
than release plus one day. The [preserved FUT-005 result](https://github.com/jhonnyisaacc/rocket/blob/dedb8e42794f47b70e68c4b7f6cec89fc48f1d6f/docs/research/futures/experiments/FUT-005-RESULT.md)
reports 24 stale-signal cash days during this disruption and a failed 2023
gross/net gate. No release-timing replay is necessary: the hypothesized
Tuesday-to-Friday lookahead is absent from its exact path. In general,
premature availability could favor a claimed information strategy by granting
access before publication; its realized bias need not have a fixed sign.
That hypothetical does not replace FUT-005's observed failure.

Annual archives retrieved later may contain revised values. Delaying a report
by ten days fixes release chronology, **not first-release vintage identity**.
FUT-005 is a conservatively release-lagged current-reported historical
replication, with that already disclosed limitation; it is not fully
reconstructed historical PIT evidence.

## Shared provider correction

`rocket/providers/cftc.py` retains positions in `as_of_date` and a UTC-midnight
`event_time` explicitly marked as date precision. Parsing alone leaves
`available_at`, `ingested_at`, `release_date`, `historical_available_at`, and
`vintage_id` unknown. It explicitly reports
`history_kind=CURRENT_REPORTED_LATEST_REPORT` and `historical_pit=false`.
It does not invent a Friday release from a Tuesday date.

Successful direct acquisition stamps `available_at` and `ingested_at` only
after the HTTP response arrives, and retains its exact content SHA-256 as
`source_sha256`. This is evidence of observed receipt of these bytes, not
the actual historical first-publication time or a CFTC revision identifier.
The OpenBB fallback likewise uses the actual clock after each adapter fetch,
not the caller's supplied evaluation time. It carries the same historical
capability disclaimer; the adapter does not expose original HTTP bytes.

`cot_context_from_result()` reports each market through the shared
`rocket.pit.PointInTime` contract. Its `knowledge_time_status` distinguishes
`ELIGIBLE`, `LATE`, and `UNKNOWN`. A known receipt after the decision suppresses
the regime as `unknown` with status `LATE`; the legacy positions-age check is
separate. Parser-only rows may remain operationally fresh but have
`knowledge_time_status=UNKNOWN`; operational `OK` must never be read as a
historical PIT assertion. Legacy adapters can supply their recorded
`ProviderResult.retrieved_at` as a conservative receipt fallback.

Seven focused regression tests cover unknown publication/vintage, actual
receipt ordering, source byte identity, backdated-decision rejection,
post-receipt eligibility, missing-clock UNKNOWN, legacy result receipts,
and the OpenBB evaluation-clock hazard. Existing CFTC/dispatch checks also
pass. FRED's current-reported-history/PIT correction is preserved untouched;
no broad ALFRED migration or historical research overwrite is part of this
change.
