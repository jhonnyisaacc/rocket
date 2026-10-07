# Job: `rocket disclosures`

One issue for this job only. Adapter: weekdays. Delayed context. **Never a buy signal.**

## Mental model

Official House + OGE = **filings**. FMP senate/house-latest = **secondary transaction rows**. Dedup by stable id. `NEW_RECORDS` means human inbox, not an error and not a trade.

```
House search + OGE API + optional FMP (FMP_API_KEY) → normalize → new vs seen
```

Trump history additionally uses the free [Open Cabinet JSON export](https://open-cabinet.org/download),
with its source OGE PDFs. These remain `secondary` rows with
`underlying_source_family=executive`. Only checked/human-verified common-stock
rows with T1 ticker resolution enter independent equity research. Bonds, funds,
unresolved symbols and disputed rows remain review items. Values remain reported
ranges. Distinct provider record IDs preserve separate same-day transactions.
The export covers published 278-T reports, not all holdings or annual disclosures.

Each row is joined to the exact person's official OGE PDF URL for the index
posting date. `disclosure_date_basis=OGE_INDEX_POSTED_DATE` identifies this date;
it is not the signature date or an assumed historical availability timestamp.
Missing joins remain unknown. Exports over 14 days old or future-dated fail closed
with `failure_kind=OC_STALE` and no transaction rows.

## Open Cabinet lag

Rocket re-fetches the Open Cabinet export on every disclosures run. It cannot force
Open Cabinet to republish. A 278-T filing (the PDF URL contains `278-T` or `278T`)
with no joined Open Cabinet transaction row sets `needs_structured_source`.
`OC_STALE` means the export is missing, future-dated, older than 14 days, or earlier
than that filing's OGE index date. `MISSING_STRUCTURED_ROWS` means the export date is
current but that PDF still has zero rows. Official rows stay `FILING_OBSERVED` /
`FILING_NOT_TRADE_ROW`. A filename is not a ticker. Until the export covers the PDF,
use Quiver or a manual read of the official PDF. That gap is not a quiet empty filing.

## OGE outage

OGE index and collection reads retry transport errors and HTTP 500–504 only:
3 attempts, sleeping 1s before the second and 2s before the third. Schema failures
and other HTTP statuses are not retried. After those attempts, executive
`ExternalOutage` is `PROVIDER_FAILURE` and `ACTION_REQUIRED`, never a silent
`NO_NEW_RECORDS`. Seen ids are only records actually returned; an outage does not
mark the OGE window as scanned. The next healthy executive fetch sets
`executive_recovery_rescan` and reports filings that were not already seen.

The records URL is read from the index HTML (`API.xsp/vN/rest` on `extapps2.oge.gov`); the highest version is used. A failed executive fetch adds `provider_status.executive.reason`, a short token with no URL or exception text. Schema tokens: `oge_index_api_marker_missing`, `oge_index_empty`, `oge_index_stale_or_future`, `oge_subject_filter_ignored`, `oge_pagination_stopped`, `oge_pagination_incomplete`, `oge_malformed_records`. Transport tokens: `transport_error`, or `http_` plus the status (`http_503`). `failure_kind` is unchanged (`InvalidProviderData` for schema, `ExternalOutage` for transport and HTTP 5xx).

## Pelosi secondary

`pelosi_secondary_history` is optional. HTTP 402/403 stay `Entitlement` and HTTP 429
stays `RateLimit` on that entry. Neither makes the overall job `PARTIAL` or
`ACTION_REQUIRED` when official House filings succeed. Official House PTR remains
the Pelosi source of truth. Entitling FMP `house-trades-by-name`, or ingesting PTR
PDFs, is a later choice. This job does not invent Pelosi trades from filing metadata.

## FMP chamber latest

`house-latest` and `senate-latest` are capped at `page=0` and `limit=25`. A larger
limit or `page>=1` returns HTTP 402 on the current plan and maps to `Entitlement`.
The cap stays in place for this plan. Broader chamber coverage stays on official
House search. `rocket disclosures` does not ingest those pages.

## Caller portfolio and watch overlap

`rocket disclosures` has no portfolio or watch flag. Overlap coverage is read from the process environment. `config/env.toml` names these variables and does not store paths.

| Book | Primary | Alias, only when the primary is unset or empty |
|---|---|---|
| portfolio | `ROCKET_PORTFOLIO_STATE` | `NAVE_PORTFOLIO_STATE_FILE` |
| watch | `ROCKET_WATCH_STATE` | `NAVE_QUANT_WATCH_STATE_FILE` |

A usable file is JSON. It is either a list of objects, or an object whose `positions` (portfolio) or `watches` (watch) value is that list. Every object needs a non-empty `ticker`. An explicit empty list is a known empty book and is `AVAILABLE`, for example `{"positions":[]}` or `{"watches":[]}`.

Unset or empty primary and alias is `NOT_CONFIGURED`. The warning names both variables. A non-empty path that cannot be read is `INVALID_CONFIGURATION` with reason `missing_file`. Invalid JSON, including a file that is not UTF-8 text, is `malformed_json`. A readable file with the wrong shape, including a missing `positions` or `watches` key or a row without `ticker`, is `schema`. The warning names the env var that supplied the path and the reason token. It does not include the path or the file contents. `cross_system_coverage.sources` records the same status, variable, alias, and reason.

Listed opportunities stay `NEEDS_REVIEW`, with `watch_proposal` cleared, while either book is not `AVAILABLE`. `missing_reference_coverage` names those books. Unknown coverage does not by itself set overall status to `ACTION_REQUIRED`.

On a healthy `NO_NEW_RECORDS` run, unchanged ticker historical opportunities leave status `NO_SETUP`. A ticker historical opportunity that is new, or whose stored fingerprint changed since `disclosure_material` in `--state-dir`, sets `ACTION_REQUIRED`. Company-name and other non-ticker review rows stay in `opportunities` and do not raise status on their own. New filings, an executive `ExternalOutage`, an Open Cabinet structured-source gap, and an executive recovery rescan still require action.

Healthy `NO_NEW_RECORDS` is success. All providers down is `PROVIDER_FAILURE`, not “no news”.

## Filters

- Official vs secondary stay separate families
- Missing FMP key: skip secondary with a warning; official still runs
- Dates on FMP rows; official PDFs may have null dates

## Live output — 2026-09-07T17:35:46Z (`main` @ `2eaa8e9`)

`operational=HEALTHY` `research=INSUFFICIENT_EVIDENCE` `research_result=NEW_RECORDS`  
`fetched_total=131` `new_total=131` (fresh state dir) `disclosure_is_not_a_buy_signal=true`

| Source | Status | Rows |
|---|---|---:|
| Official House | OK | 3 |
| Official OGE | OK | 21 |
| FMP secondary | OK (200 fetched, then deduped) | 107 |

Sample secondary:

| Filer | Asset | Type | Date |
|---|---|---|---|
| Jonathan Jackson | VSAT | Sale | 2026-08-28 |
| Cleo Fields | AAPL | Purchase | 2026-08-13 |
| Michael Rulli | ALL | Sale | 2026-08-12 |
| Michael Rulli | EQIX | Purchase | 2026-08-07 |
| John J. McGuire | AAPL | Sale | 2026-08-18 |
| John McGuire | NVDA | Purchase | 2026-08-18 |
| Kevin Hern | NKE | Sale | 2026-08-13 |
| Kevin Hern | MSFT | Sale | 2026-08-21 |
| Kevin Hern | BA | Sale | 2026-08-13 |
| Kevin Hern | DIS | Sale | 2026-08-10 |

## Review / polish

- [ ] Split official filings vs secondary rows in presentation
- [ ] Display-dedup `John McGuire` / `John J. McGuire` without merging engine identities
- [ ] Banner: delayed context, independent portfolio evidence
- [ ] `NEW_RECORDS` should look like inbox, not error

Contract: JSON `ResearchResult`. Operational ≠ research. `execution_enabled` false.
