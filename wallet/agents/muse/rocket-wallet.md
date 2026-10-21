---
name: rocket-wallet
description: Operate the Rocket agentic wallet through its MCP tools. Use for listing resolution, dry-run swaps, rebalance plans, provider health, and wallet status. Never use for live sends without a human approval step.
---

# Rocket Wallet

You operate the Rocket wallet through its MCP server. The tools are `wallet_status`, `resolve_alert`, `request_swap`, `request_listing`, and `plan_rebalance`. Load the `rocket-get-started` skill before widening access, the `rocket-pay-and-swap` skill before moving money, and the `rocket-x402-services` skill before paying for a service.

Start with `wallet_status`. Name the mode, the enabled chains, the support tiers, and the caps before any other call. Check `/provider-health` on the executor when a route fails, and name the provider and error class in your report.

Never ask for a seed phrase, a private key, a passphrase, or a Turnkey secret. Never print a token or a signed payload. `request_swap` is a dry-run and broadcasts nothing. `plan_rebalance` returns `would_send` and moves nothing. A live `request_listing` under any mode but `autonomous` returns `pending_approval`. Stop there and tell the human which step waits.

Treat a trade as done only on a terminal landed status with a transaction hash. A quote is not a fill. If a tool fails closed, report the reason as the answer. Caps, allowlists, support tiers, and approval modes belong to the human.
