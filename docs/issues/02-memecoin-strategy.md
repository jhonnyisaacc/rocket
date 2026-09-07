# Memecoin strategy — NO EDGE VALIDATED; primitives only

Status: open tracking issue. Not a V1 live agent job.

## Why it is not live

- Canonical NAVE state: **NO EDGE VALIDATED**. M3 statistical sanity was inconclusive (Day-2 event panel not exported; A/B/C/D not estimated).
- Participant self-flow contaminated raw flow (~47% of a first-30-minute slice). Unknown must stay unknown.
- Collector architecture failed: WebSocket → SQLite insert/page I/O → `MAX_QUEUE_DEPTH` overflow. Redesign is spool-first; strategy work is blocked on stable capture.
- Only a handful of comparable event days. Case studies are not defaults. Symbols are not join keys.
- Python cannot win launch-block sniping; that was never the research claim.

## Keep in Rocket

`rocket memecoin collect|scan|evaluate|status` primitives and the raw spool. Status always carries `edge: NO_EDGE_VALIDATED`.

## Do not

Schedule a strategy/chat job, inspect holdout as health, or add asset-specific overfit rules.
