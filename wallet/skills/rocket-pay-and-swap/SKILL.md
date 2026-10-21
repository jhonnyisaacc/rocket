---
name: rocket-pay-and-swap
description: Details for moving money with Rocket that the standing instructions do not carry. It covers units, the checks before spending, and what a bridge plan does not do. Use when asked to swap, send, withdraw, or rebalance.
license: MIT
---

# Moving money. The details that bite

## Before spending anything

Read `wallet_status` first. Check that the chain is enabled and that the balance covers the amount plus fees. A buy also pays the token account rent on Solana on its first purchase. Name that cost before the trade.

## Amounts are in the smallest unit at every boundary

A swap intent carries a human amount plus its decimals. The send path converts it once. Never pass a decimal figure where the tool asks for the smallest unit. USDC has 6 decimals. SOL has 9. An EVM native amount has 18.

## A dry-run is the default

`request_swap` always runs dry_run. It broadcasts nothing, even when the process is live. Only `request_listing` can broadcast, and only under an `autonomous` grant after screening, simulation, the spend reservation, and the signing policy. If any check fails, the trade does not send. Treat that as the answer, not as a prompt to retry louder.

## Read the recipient back

A withdraw moves real funds and cannot be undone. Read the destination back to the user before a human approves it. The destination must sit on the owner allowlist. A token recovery destination must sit on its own allowlist.

## A bridge plan is not a bridge

`plan_rebalance` returns `would_send`. Nothing bridges. Do not tell the user that funds moved. A same-chain swap must finish with a terminal status before a dependent order starts.

## Confirm before you report

Treat a trade as done only on a terminal landed status with a transaction hash. A quoted route is not a fill. A submitted transaction is not a fill.
