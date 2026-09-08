# Job: `rocket portfolio review`

One issue for this job only. Daily. Caller owns theses and the book (`--state PATH`).

## Mental model

Rocket reviews **holdings**, not a candidate list. Wallet inventory is optional, read-only, never creates positions or overwrites theses.

```
--state JSON → optional --refresh-inventory (Helius/RPC) → per-ticker HOLD / REVIEW / REDUCE / EXIT
```

Address: `state.wallet_address` or `ROCKET_INVENTORY_ADDRESS`. Refresh without an address is operational failure, not a silent skip.

## Filters

- Per-position evidence: thesis present, market quote fresh, macro optional
- Inventory: known ONDO mints update quantity; unknown `*ondo` mints → `pending_review` only
- Failed inventory fetch → `PARTIAL`/`UNAVAILABLE`, not fake HEALTHY
- Empty book → `CALLER_STATE_MISSING`, not `NO_SETUP`

## Live output

No capture in the 2026-09-07T17:35Z run (needs caller `--state`).

Paste the next `rocket portfolio review --state PATH --json` here.

## Review / polish

- [ ] Per-holding table: action, quantity, thesis status, evidence
- [ ] Surface `pending_review` mints
- [ ] Human decision required stays visible

Contract: JSON `ResearchResult`. Operational ≠ research. `execution_enabled` false.

Mixed results preserve valid action transitions even when another ticker lacks
evidence. `position_diagnostics` identifies affected tickers; typed reasons name
the missing dimensions or failed providers. Inventory diagnostics appear only
when reconciliation was requested and failed. Diagnostic-only positions do not
overwrite the previous action used for later transition detection.
