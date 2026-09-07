# Job: `rocket watch check`

One issue for this job only. Adapter cadence ~3× daily.

## Mental model

Caller owns the watch list (`--watches PATH`). Rocket evaluates ABOVE / BELOW / CROSS_* / ZONE against quotes. Silent unless a rule **enters**. Rocket never creates or deletes watches.

```
watches file → Yahoo (or --prices-file) → each rule true/false vs last price → JSON
```

Empty result = no rule entered. That is success, not a provider failure.

## Filters

- Identity: listed EQUITY/ETF only; unexpected name/exchange → mapping required, not a fire
- Freshness: session clock; stale quote does not fire
- Fire only on **entry**, not continuous true

## Live output

No capture in the 2026-09-07T17:35Z run (needs caller watch file).

Paste the next `rocket watch check --watches PATH --json` here.

## Review / polish

- [ ] Present only newly entered rules (ticker, condition, price, citation)
- [ ] Distinguish `NO_SETUP` (nothing entered) from `UNAVAILABLE` (Yahoo down)
- [ ] Keep watches caller-owned in the copy

Contract: JSON `ResearchResult`. Operational ≠ research. `execution_enabled` false.
