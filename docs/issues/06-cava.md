# Job: `rocket cava`

One issue for this job only. Adapter cadence ~daily 18:00 BA. Overlay only — never required by crypto or portfolio.

## Mental model

```
Cava RSS → newest unprocessed video → transcript (Supadata) → claims → FRED corroboration
```

Cursor advances on a fully validated overlay, or after a transcript-only summary
handoff is durably saved. The latter never creates a validated overlay. Missing
Cava does not block other jobs.

When no supported exact measure is identified, `report_type=TRANSCRIPT_SUMMARY`
returns the full transcript in `summary_request` for the caller bot to summarize
the most important claims and lessons. The bot follows `task` and `instructions`,
treats the transcript as source material, and attributes statements to Cava.
`summary_status=AWAITING_CALLER_BOT` means Rocket has prepared the handoff, not
generated model prose. The persisted run is the retry source if bot presentation
fails. A named measure whose provider fails stays diagnostic; it cannot take this
summary shortcut. Unsupported commentary remains unverified.

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
