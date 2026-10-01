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

ISM decisions use a separate `technical_basis.ism_daily_basis` snapshot from
Yahoo daily-bar timestamps. Only completed NY sessions are eligible (using the
exchange calendar and its existing 20-minute post-close finalization delay).
The assessed close `C` is the latest completed daily close; support `S` is the
minimum of the **20 completed closes preceding C**, excluding C. Partial bars
cannot lower support or change the decision. Shared live technical fields and
short/disclosures gates retain their existing behavior. Missing/stale completed
close evidence yields NEEDS_REVIEW, with no quote substitution.

Calculate simple 14-session ATR from the same completed OHLC snapshot as the
mean of `max(high-low, abs(high-prev_close), abs(low-prev_close))`, excluding the
assessed bar. Invalid/misaligned prior OHLC cannot produce ATR. Let
`V = clamp(ATR14, 0.005*S, 0.03*S)`. The fixed nominal zone is
`[S - 0.5*V, S + V]`, and research invalidation is `S - 1.5*V`. Missing ATR uses
`V = 0.02*S`, explicitly labelled `low_20_percent_fallback`; valid ATR uses
`low_20_atr_support`. Output includes `raw_atr`, `volatility_clamped` (true only
when valid ATR hits the floor/cap), and the effective volatility unit.

Status is close-based:

- `C < S`: WATCH, “closed below support <S>, wait for close back above support”.
  The ATR invalidation is a separate risk level and never overrides this veto.
- `S <= C <= zone_high - 0.1*V`: BUY_CANDIDATE, if fundamentals pass.
- Otherwise: WATCH, “wait for pullback to <zone>”, including the buffered close
  threshold in the reason.

The default entry buffer is **0.1V** (10% of the effective, bounded volatility
unit). It provides an entry margin at the zone top; it is not a stateful
latching rule. Equality at support and the buffered threshold is eligible.
Zones never stretch to intraday prices, including for broken names. Intraday
quote and its separate signed distance are informational; a quote recovery
cannot clear a closing support veto, and a quote crossing the top cannot flip an eligible close.
`latest_completed_close`, its timestamp, `status_basis`, `status_basis_date`,
`buy_close_threshold`, and the buffer fraction make the decision auditable.
Every passing-name reason includes “as of YYYY-MM-DD close”, using the NY
session date the status is graded on. These remain research heuristics, not a validated trading edge or execution instruction.

`rocket ism --json` adds top-level `watchlist_handoff`, also retained in
`payload.watchlist_handoff`. Every passing long, including a vetoed WATCH,
supplies ticker, industry, status, zone bounds, invalidation, quote/distance,
close/buffer inputs, volatility labels, reason and data provenance.
`distance_to_zone_pct` (also exposed as `distance_pct`) now uses the completed
close, matching status. `intraday_price` is an explicit alias of the retained
`current_price` quote, and `intraday_distance_pct` reports its separate distance.
Both signed distances use the nearest nominal zone boundary as denominator:
negative below, zero inside, positive above. Zero means inside the nominal band;
it does not imply the close passed the support veto or buffered buy threshold.
`stop_level` is retained solely as a backward compatible **exact alias of invalidation**, not another stop calculation.
Candidate invalidation is `S - 1.5V` whenever a zone exists, and null otherwise
(NEEDS_REVIEW, NOT_INTERESTING and SHORT_INPUT). This is a semantic change from
the old `invalidation = low_20` field. The original live technical low is preserved as `low_20_close` on ISM long rows,
including non-passing rows; it is support context, not the ATR risk level. It may
differ from `entry.support`, which uses the completed-session snapshot. Yahoo
history provider attempts include `retrieved_at` on success and failure. No watch is installed automatically;
`execution_enabled` remains false. Short `ism_simple` gates and the
`valuation_support` veto are unchanged.
