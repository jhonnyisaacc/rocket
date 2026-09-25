# MC-003 frozen design — exit feasibility and independent replication

Parent: MC-002. Status: frozen design before a new independent cohort. MC-002's 12 unavailable exits and 10 missing entry fee states motivate this experiment; its small positive evaluation quote subset is **not** a reason to retune the score.

Run one new 300-second, 256 MiB maximum read-only Pump log session. Reuse the same pinned IDL, independent signature reconciliation, native-SOL/non-Mayhem population, t0+5s feature snapshot, curve-progress score, 0.01 SOL size, t0+7s entry, t0+67s exit, observed as-of fee rates, 2% adverse slippage each leg and 155,000-lamport per-leg network scenario. Preserve all creates, unsupported regimes, failures and missing states. No threshold or cost adjustment is allowed from MC-002.

Use `rocket.memecoin.pit-snapshot.v2` to include the observed quote mint in the row fingerprint. This repairs a metadata-fingerprint omission found in MC-002; numeric features, scoring and outcomes are unchanged.

**Separate outcome 1, risk:** among launches with a quoteable hypothetical entry, does the t0+67s state support a sell of the stressed token inventory? Report `EXIT_FEASIBLE`, `EXIT_UNAVAILABLE` and `UNKNOWN` (coverage or input failure) for every candidate, by score quartile and chronological split. Do not call `EXIT_UNAVAILABLE` an observed rug without transaction-level confirmation.

**Separate outcome 2, economic stress:** for a quoteable entry, use MC-002's net quote proxy when exit is feasible. In an explicit worst-case terminal-liquidity scenario, value an unavailable exit at zero cash recovery, charge the entry and network costs, and retain that loss in the ranked universe. Also report MC-002-style quoted-only numbers for comparability. This is a stress bound, not a realized liquidation price. A missing entry fee state remains `UNKNOWN` and is never silently replaced by a fill.

Keep the 70/30 chronological split. Compare the unchanged curve-progress top quartile with the complete eligible population; report censoring and exit feasibility before any return metric. The cheap falsifier is whether the ranking remains plausible once exit failures are counted as risk. A positive result only permits a stricter execution/latency test and larger prospective sample. No signal or Rocket decision is promoted from this experiment alone.
