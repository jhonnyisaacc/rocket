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

## Movement evidence and caller ownership

The caller owns the configured wallet, position list, and approved theses; pass
`wallet_address` in the state file and request `--refresh-inventory`. Rocket's
inventory and review caches are wallet-associated observations, not portfolio
configuration. Do not duplicate caller configuration in the environment.

Inventory records include `observed_at`. A changed known mint, including a partial
increase/decrease, includes `movement` with previous/current quantities, bounded
transaction evidence (signature, mint, delta, block time/timestamp), and explicit
history coverage. Signatures shared by owner/token accounts are deduplicated;
transactions older than the prior observation are excluded where timestamped.
History failures do not invalidate independently verified balances. Zero-balance
confirmation still requires agreeing fresh RPC snapshots. Transfers and
unclassified flows are never silently converted into sales or realized P&L.

Review notification state advances even if a thesis remains draft, preventing
unchanged inventory from repeatedly generating an alert. Diagnostic rows never
become approved investment actions. Changing wallet input resets review dedupe.
