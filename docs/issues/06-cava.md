# Job: `rocket cava`

One issue for this job only. Adapter cadence ~daily 18:00 BA. Overlay only — never required by crypto or portfolio.

## Mental model

```
Cava RSS → newest unprocessed video → transcript (Supadata) → claims → FRED corroboration
```

Cursor advances only on a fully validated overlay. Missing Cava does not block other jobs.

## Filters

- Dedup RSS ids; newest first
- Transcript unavailable → do not advance cursor
- Corroboration fail-closed; contradictions listed
- Warnings must not stringify HTTP URLs (API keys)

## Live output

No capture in the 2026-09-07T17:35Z run (needs `SUPADATA_API_KEY` + RSS).

Paste the next `rocket cava --json` here.

## Review / polish

- [ ] Show claims, corroboration status, contradictions, `cursor_advanced`
- [ ] “No new video” = `HEALTHY` / `NO_SETUP`
- [ ] Label as overlay, not a trade

Contract: JSON `ResearchResult`. Operational ≠ research. `execution_enabled` false.
