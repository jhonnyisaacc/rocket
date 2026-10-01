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

NAPM fallback is an explicit workflow input for callers with an independently
acquired monthly observation: `napm={"reference_month": "YYYY-MM", "value": 54.6}`.
It only fills a missing manufacturing headline for the matching month; it never
overrides a publisher headline or supplies the services composite. The CLI uses
publisher reports and does not acquire or imply a live NAPM fallback.

## Long entry zones and watchlist handoff

Current expanding industries with reviewed company exposure feed the long
screen. Existing evidence/freshness checks and fundamentals gates remain:
EPS growth >= 0 and 0 < trailing P/E <= 40. Missing evidence stays NEEDS_REVIEW;
failing fundamentals stay NOT_INTERESTING.

ISM longs use prior 20-session **closing** support `S = low_20` (the history
provider excludes the latest close), rather than the old moving-average reclaim
band. From the same Yahoo daily OHLC response, calculate simple 14-session ATR
as the mean of `max(high-low, abs(high-prev_close), abs(low-prev_close))`,
excluding the latest potentially partial daily bar. Missing, misaligned or invalid
prior OHLC bars cannot produce ATR.

Let `V = clamp(ATR14, 0.005*S, 0.03*S)`. The nominal entry zone is
`[S - 0.5*V, S + V]`, with research invalidation at `S - 1.5*V`. The floor and
cap avoid near-zero bands and excessively wide stops. If ATR is unavailable,
use `V = 0.02*S` and explicitly label `entry.method` and handoff provenance
`low_20_percent_fallback`; otherwise the method is `low_20_atr_support`.

A current quote **or latest close** strictly below invalidation stays WATCH:
“falling below support, wait for stabilization”. The shared provider's raw
`breakdown` flag denotes any new closing low; ISM uses the buffered price/close
threshold so a small new low is not an automatic veto. An explicit breakdown
without a valid latest close remains a conservative WATCH for legacy contexts.
Otherwise price <= zone high is BUY_CANDIDATE, including below-zone discounts;
price > zone high is WATCH: “wait for pullback to <zone>”. Weak technicals alone
are not a veto. For weak or tolerated raw-breakdown quotes below the nominal
lower edge, extend that edge to the current price. This includes a discount
without giving the watcher a reclaim band above its price. The stop and upper
edge remain anchored to prior support. These are deterministic volatility-aware
research heuristics, not a validated trading edge or execution instruction.

`rocket ism --json` adds a top-level `watchlist_handoff` array, also retained in
`payload.watchlist_handoff` for stored-result consumers. Every passing long,
including a guarded WATCH, supplies ticker, industry, status, zone bounds,
invalidation/stop, current price, reason, breakdown flag, and provenance for the
ISM release, exposure, quote, technical basis (ATR, latest close and volatility unit), and fundamentals. Distance is
signed percent to the nearest zone boundary (boundary as denominator): negative
below, zero inside, positive above. Existing candidate fields remain available.
No watch is installed automatically; `execution_enabled` remains false.
Disclosures' entry policy, `ism_simple` short gates, and `valuation_support` veto
are unchanged.
