# Job: `rocket ism`

One issue for this job only. Adapter: month days 1–7 after publication.

## Mental model

Headline PMI and industry rankings are **separate**. Never treat NMFBAI as the services composite. NAPM may fill manufacturing headline for the matching month only.

```
live: sitemap roundup → PR Newswire HTML → parse
replay: --manufacturing-html / --services-html
```

## Filters

- Kind must match heading (manufacturing vs services)
- Month from URL/heading; `Unknown` must not reach identity
- Rankings from “industries reporting growth/contraction” before respondent quotes
- Unpublished / stale identity is explicit

## Live output — 2026-09-07T17:35:46Z (`main` @ `2eaa8e9`)

Publisher fetch **failed closed**. Sitemap found August 2026 roundups; HTML month parsed as `Unknown` (would crash identity if passed through). Workflow: `operational=UNAVAILABLE` both series.

Roundups:

- manufacturing: `.../ism-pmi-reports-roundup-august-2026-manufacturing/`
- services: `.../ism-pmi-reports-roundup-august-2026-services/`

## Review / polish

- [ ] Parser must not emit `report_month=Unknown`; fail the fetch instead of crashing
- [ ] Follow PR Newswire from those roundup pages
- [ ] Display headline PMI and industry lists on separate lines

Contract: JSON `ResearchResult`. Operational ≠ research. `execution_enabled` false.
