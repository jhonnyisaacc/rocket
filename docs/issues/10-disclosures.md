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
Missing joins remain unknown. Exports over 14 days old or future-dated fail closed.

Caller portfolio/watch coverage must be known before proposing an entry or watch.
Absent, unreadable or malformed caller reference files leave listed opportunities
`NEEDS_REVIEW`, clear `watch_proposal`, and expose `missing_reference_coverage`.
Only an explicitly supplied, valid empty list establishes an empty book/watch
list. Known matches may still be shown, but do not imply complete overlap coverage.

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
