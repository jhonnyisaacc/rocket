# Scheduled research: inventory completeness audit

Research-only offline pass, September 16, 2026. No API calls or new Helius credits. No live monitoring or trading enabled; NO_EDGE_VALIDATED unchanged.

## Method and result

Read the cached historical_cohort_sample ledger (100 transactions). Exclude failed transactions, order by block timestamp and slot, aggregate integer owner token deltas per canonical mint. Starting observed inventory at zero is a coverage diagnostic, not a claim that actual starting inventory was zero. Within-slot order is not resolved; conclusions about intra-slot deficits require transaction-order verification.

13 distinct mints have nonzero owner token flows. Twelve have both inbound and outbound flows and sum to zero net raw tokens within the cached page. One mint, `Co3KdYRY2hchwjhV58FQE2A1bi7bxUTntQgJu6A3GLSj`, has an outbound event without a preceding observed acquisition, leaving -15,849,512,476,909 raw units in this artificial zero-start inventory. That position cannot have defensible cost basis from the current page alone.

Zero net flow for the other twelve does not prove complete trade histories: offsetting transfers, missing earlier cycles, opening balances and partial API coverage remain possible. Do not count twelve successful trades or compute win rate from this diagnostic.

## Specific next experiment

Prioritize one minimal candidate cycle for instruction-level verification: Solana mint `435CfmvrJ4QtkVv4cZ1TbUa7rzrKKjvQJLMnvhTCpump` has one observed inflow and one observed outflow with zero net tokens. Inspect both raw transactions for owner authority, swap route, native/WSOL payment reconciliation, rent and fees, plus any failed transactions nearby. Keep the missing-acquisition mint excluded from return estimates unless its opening acquisition is recovered. Then repeat across the other eleven balanced mints, preserving losses and unknowns.

The latest Fomo fill match has already been communicated to the user; this preliminary inventory audit does not establish an edge or require user action. No duplicate notification warranted.
