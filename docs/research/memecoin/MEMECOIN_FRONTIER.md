# Memecoin Frontier

Status: current, 2026-09-24. One live question; update after each accepted or rejected experiment.

**Question:** Which features genuinely observable during the earliest token lifecycle contain information about later economically tradable outcomes after realistic execution?

## Current bottleneck

No `main` collector provides a complete, timestamped early-launch universe with decoded protocol state and a measured receive delay. The raw spool is durable and records receipt time, but the CLI accepts supplied frames; it does not subscribe to a feed, decode creation/trade events or attest coverage. #27 has selected historical wallets and state windows; #30 samples mostly graduated/window-closed coins. Neither is an unbiased early-launch observation panel. Both are useful for decoder, accounting and failure tests, not for a new early-edge estimate.

## Next falsifiable step

Create a bounded, read-only prospective collection session of **all** observed Pump create events and subsequent curve events in a frozen UTC window. Preserve raw bytes, slot/signature/instruction order, first receive and decode times, source gaps, protocol/fee version and source hash. Reconcile the observed create count against an independent program-signature index for the same window. If coverage or receive timing cannot be established, mark the panel incomplete and use it only for decoder work.

For each mint, freeze observation rows at actual measured availability checkpoints tied to events (creation receipt, first state change and later pre-declared age/curve milestones). Keep late/missing observations explicit. Only after features and the negative universe are frozen, acquire later protocol and trade outcomes. Compare an age/curve-only baseline with feature-family ablations; use temporal splits and size-aware costed entry/exit simulation. The first cheap falsifier is whether early states can be reconstructed without future information and with enough coverage to bound selection bias. The economic falsifier is whether top-ranked names outperform a simple time-eligible baseline after failure and cost stress.

## Decision today

Status `OPEN`: **data barrier, not an edge finding**. No model or signal is promoted. The snapshot validator in `rocket/research/memecoin_dataset.py` creates deterministic feature rows from independently decoded observations; it does not solve source coverage or outcome availability. The experiment ledger records the first experiment as blocked before outcome inspection.
