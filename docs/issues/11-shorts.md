# Job: `rocket shorts`

One issue for this job only. Adapter: weekdays. Research only.

## Mental model

ISM-specific live Shorts research is intentionally small and explainable. The
canonical live path starts with an ISM contracting industry, then checks one
Yahoo price condition and one FMP company-fundamentals condition. Missing data
stays UNKNOWN, never false.

```
ISM contracting → Yahoo technical breakdown + FMP bearish fundamentals → selected or rejected with reason
```

## Filters

Canonical ISM live path requires exactly three observed conditions:

- `ism_contracting`: the stored ISM candidate source has `direction=short`.
- `technical_breakdown`: Yahoo close is below the prior 20-session low.
- `company_fundamentals`: FMP's current bearish EPS-growth flag is true.

`valuation_support=True` remains a safety veto when FMP provides it. Sector
weakness, catalyst, earnings revisions and positioning are retained as context
but are not required for the ISM list. Explicit `--input-file` replay keeps the
generic factor scorer for non-ISM snapshots.
Yahoo quote PIT: `available_at` ≤ decision time, age ≤ 5d.

Live universe: bearish candidates produced by `rocket ism` or `rocket disclosures`
in the same `--state-dir`. Run one of those upstream jobs first; there is no
built-in AAPL/NVDA/TSLA/JPM fallback. Missing or stale candidate acquisition stays
diagnostic. `--input-file` remains available for explicit research snapshots.
The four-name universe in the historical captures below predates this change.

## Live output — 2026-09-07T17:35:46Z (`main` @ `2eaa8e9`)

`operational=HEALTHY` `research=INSUFFICIENT_EVIDENCE`

This capture: all four rejected **`available_after_decision_time`** (Yahoo available_at after decision clock). PIT fail-closed. No factor matrix.

Earlier same-day run with eligible quotes (FMP PE live, EPS growth missing):

| Ticker | Tech | Fundamentals | Earnings rev. | Valuation | Macro | Sector | Result |
|---|---|---|---|---|---|---|---|
| AAPL | no | unknown | no | no (PE ~36.5) | neutral | no | insufficient evidence |
| NVDA | no | unknown | no | no (PE ~29) | neutral | no | insufficient evidence |
| TSLA | no | unknown | no | no (PE ~300) | neutral | yes | insufficient evidence |
| JPM | no | unknown | no | no (PE ~15.4) | neutral | no | insufficient evidence |

Selected: none.

## Review / polish

- [ ] Show PIT reject separately from “not enough factors”
- [ ] Factor matrix: OBSERVED vs UNKNOWN vs failed flag
- [ ] Label FMP PE even when EPS growth is missing
- [ ] Confirm this four-name universe

Contract: JSON `ResearchResult`. Operational ≠ research. `execution_enabled` false.
